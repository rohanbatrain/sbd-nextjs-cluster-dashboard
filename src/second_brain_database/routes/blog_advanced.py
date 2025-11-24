"""
# Blog Advanced Features Routes

This module provides **specialized API endpoints** for advanced blog functionality,
focusing on content safety, SEO optimization, and audience analytics.

## Domain Overview

These endpoints extend the core blog platform with enterprise-grade features:
- **Data Safety**: Real-time autosave and version restoration.
- **Discoverability**: Automated SEO tools (Sitemaps, RSS).
- **Growth**: Newsletter subscriptions and engagement tracking.

## Key Features

### 1. Content Safety & Versioning
- **Autosave**: High-frequency, non-destructive saving of draft content.
- **Version History**: Full audit trail of content changes.
- **Restoration**: Ability to revert a post to any previous state.

### 2. SEO & Discovery
- **Sitemap.xml**: Dynamic generation of sitemaps for search engine indexing.
- **RSS Feed**: Standard RSS 2.0 feeds for content syndication.
- **Metadata**: Rich schema.org compatible metadata support.

### 3. Analytics & Growth
- **Event Tracking**: Privacy-focused tracking of views, shares, and bookmarks.
- **Engagement Metrics**: Aggregated stats for content performance analysis.
- **Newsletter**: Built-in subscription management for audience building.

## API Endpoints

### Versioning
- `POST .../autosave` - Save draft state
- `GET .../versions` - View revision history
- `POST .../restore` - Revert to version

### SEO
- `GET .../sitemap.xml` - Search engine index
- `GET .../rss.xml` - RSS feed

### Analytics
- `POST /blog/analytics/track` - Record user event
- `POST .../newsletter/subscribe` - Capture lead

## Usage Examples

### Autosaving Content

```python
# Called by frontend editor every 30s
await client.post(f"/blog/websites/{wid}/posts/{pid}/autosave", json={
    "content": "<p>Draft content...</p>"
})
```

### Restoring a Version

```python
await client.post(f"/blog/websites/{wid}/posts/{pid}/restore", json={
    "version_id": "version_abc123"
})
```

## Module Attributes

Attributes:
    router (APIRouter): FastAPI router for advanced blog features
"""

from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from second_brain_database.routes.blog_dependencies import (
    require_access_author,
    require_access_viewer,
)
from second_brain_database.managers.logging_manager import get_logger
from second_brain_database.models.blog_models import (
    AutoSavePostRequest,
    BlogVersion,
    RestoreVersionRequest,
    NewsletterSubscribeRequest,
    NewsletterSubscriberResponse,
    TrackAnalyticsRequest,
    EngagementMetricsResponse,
)

logger = get_logger(prefix="[Blog Additional Routes]")

router = APIRouter(prefix="/blog", tags=["blog-advanced"])


# Auto-save endpoints
@router.post("/websites/{website_id}/posts/{post_id}/autosave")
async def autosave_post(
    website_id: str,
    post_id: str,
    request: AutoSavePostRequest,
    current_user: dict = Depends(require_access_author),
):
    """
    Save a temporary draft of the post content (Auto-save).

    This endpoint is designed to be called frequently (e.g., every few seconds) by the
    frontend editor to prevent data loss. It updates a separate `auto_save_content` field
    without creating new versions or affecting the published content.

    **Behavior:**
    *   Updates `auto_save_content` and `auto_save_at`.
    *   Does NOT create a revision history entry.
    *   Does NOT change the `updated_at` timestamp of the main post.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post.
        request (AutoSavePostRequest): The content to save.
        current_user (dict): The authenticated user.

    Returns:
        dict: Success message and timestamp.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        # Update auto-save content
        result = await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post_id, "website_id": website_id, "author_id": current_user["_id"]},
            {
                "$set": {
                    "auto_save_content": request.content,
                    "auto_save_at": datetime.utcnow(),
                }
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Post not found or access denied")

        logger.info("Auto-saved post: %s", post_id)
        return {"message": "Auto-save successful", "saved_at": datetime.utcnow()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to auto-save post: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to auto-save post")


# Version history endpoints
@router.get("/websites/{website_id}/posts/{post_id}/versions", response_model=List[BlogVersion])
async def get_post_versions(
    website_id: str,
    post_id: str,
    current_user: dict = Depends(require_access_viewer),
):
    """
    Retrieve the revision history of a post.

    Returns a list of all saved versions for a post. Versions are created automatically
    when a post is updated via the main update endpoint.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post.
        current_user (dict): The authenticated user.

    Returns:
        List[BlogVersion]: A list of past versions.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one(
            {"post_id": post_id, "website_id": website_id}
        )

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        versions = post_doc.get("revision_history", [])
        return [BlogVersion(**v) for v in versions]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get post versions: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get versions")


@router.post("/websites/{website_id}/posts/{post_id}/restore")
async def restore_post_version(
    website_id: str,
    post_id: str,
    request: RestoreVersionRequest,
    current_user: dict = Depends(require_access_author),
):
    """
    Revert a post to a previous version.

    This endpoint allows authors to undo changes by restoring content from the revision history.

    **Process:**
    1.  Locates the requested version by ID.
    2.  Creates a *new* version backup of the *current* state (safety net).
    3.  Overwrites the current post content with the data from the restored version.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post.
        request (RestoreVersionRequest): The ID of the version to restore.
        current_user (dict): The authenticated user.

    Returns:
        dict: Success message.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        # Get the post and find the version
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one(
            {"post_id": post_id, "website_id": website_id}
        )

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Find the version to restore
        version_to_restore = None
        for version in post_doc.get("revision_history", []):
            if version.get("version_id") == request.version_id:
                version_to_restore = version
                break

        if not version_to_restore:
            raise HTTPException(status_code=404, detail="Version not found")

        # Save current state as a new version before restoring
        current_version = BlogVersion(
            version_id=f"version_{uuid4().hex[:16]}",
            post_id=post_id,
            title=post_doc["title"],
            content=post_doc["content"],
            excerpt=post_doc.get("excerpt"),
            created_at=datetime.utcnow(),
            created_by=current_user["_id"],
            change_summary="Pre-restore backup",
        )

        # Restore the version
        result = await db_manager.get_tenant_collection("blog_posts").update_one(
            {"post_id": post_id, "website_id": website_id},
            {
                "$set": {
                    "title": version_to_restore["title"],
                    "content": version_to_restore["content"],
                    "excerpt": version_to_restore.get("excerpt"),
                    "updated_at": datetime.utcnow(),
                },
                "$push": {"revision_history": current_version.model_dump()},
            },
        )

        if result.modified_count == 0:
            raise HTTPException(status_code=500, detail="Failed to restore version")

        logger.info("Restored version %s for post: %s", request.version_id, post_id)
        return {"message": "Version restored successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to restore version: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to restore version")


# SEO endpoints
@router.get("/websites/{website_id}/sitemap.xml")
async def get_sitemap(website_id: str):
    """
    Generate a standard XML sitemap for the website.

    This endpoint dynamically generates a sitemap listing all *published* posts.
    It is used by search engine crawlers (Google, Bing) to index the blog.

    **Format:**
    Standard XML Sitemap Protocol 0.9.

    Args:
        website_id (str): The ID of the website.

    Returns:
        Response: XML content with `application/xml` media type (implicit in FastAPI default, but usually explicit Response is better).
    """
    try:
        from second_brain_database.database import db_manager

        # Get all published posts
        posts = []
        async for post in db_manager.get_tenant_collection("blog_posts").find(
            {"website_id": website_id, "status": "published"}
        ).sort("updated_at", -1):
            posts.append(post)

        # Generate XML
        sitemap_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        sitemap_xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

        for post in posts:
            sitemap_xml += "  <url>\n"
            sitemap_xml += f'    <loc>https://yourdomain.com/blog/{website_id}/{post["slug"]}</loc>\n'
            sitemap_xml += f'    <lastmod>{post["updated_at"].isoformat()}</lastmod>\n'
            sitemap_xml += "    <changefreq>weekly</changefreq>\n"
            sitemap_xml += "    <priority>0.8</priority>\n"
            sitemap_xml += "  </url>\n"

        sitemap_xml += "</urlset>"

        return sitemap_xml

    except Exception as e:
        logger.error("Failed to generate sitemap: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate sitemap")


@router.get("/websites/{website_id}/rss.xml")
async def get_rss_feed(website_id: str):
    """
    Generate an RSS 2.0 feed for the website.

    Allows users to subscribe to the blog using RSS readers.
    Includes the 20 most recent *published* posts.

    Args:
        website_id (str): The ID of the website.

    Returns:
        Response: XML content.
    """
    try:
        from second_brain_database.database import db_manager

        # Get website info
        website_doc = await db_manager.get_tenant_collection("blog_websites").find_one({"website_id": website_id})
        if not website_doc:
            raise HTTPException(status_code=404, detail="Website not found")

        # Get recent published posts
        posts = []
        async for post in (
            db_manager.get_tenant_collection("blog_posts")
            .find({"website_id": website_id, "status": "published"})
            .sort("published_at", -1)
            .limit(20)
        ):
            posts.append(post)

        # Generate RSS XML
        rss_xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        rss_xml += '<rss version="2.0">\n'
        rss_xml += "  <channel>\n"
        rss_xml += f'    <title>{website_doc["name"]}</title>\n'
        rss_xml += f'    <description>{website_doc.get("description", "")}</description>\n'
        rss_xml += f'    <link>https://yourdomain.com/blog/{website_id}</link>\n'

        for post in posts:
            rss_xml += "    <item>\n"
            rss_xml += f'      <title>{post["title"]}</title>\n'
            rss_xml += f'      <description>{post.get("excerpt", "")}</description>\n'
            rss_xml += f'      <link>https://yourdomain.com/blog/{website_id}/{post["slug"]}</link>\n'
            rss_xml += f'      <pubDate>{post.get("published_at", post["updated_at"]).strftime("%a, %d %b %Y %H:%M:%S GMT")}</pubDate>\n'
            rss_xml += "    </item>\n"

        rss_xml += "  </channel>\n"
        rss_xml += "</rss>"

        return rss_xml

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to generate RSS feed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate RSS feed")


# Newsletter endpoints
@router.post("/websites/{website_id}/newsletter/subscribe", response_model=NewsletterSubscriberResponse)
async def subscribe_to_newsletter(
    website_id: str,
    request: NewsletterSubscribeRequest,
):
    """
    Subscribe a user to the website's newsletter.

    This is a public endpoint (no auth required) allowing visitors to sign up for updates.

    **Logic:**
    *   If the email is new: Creates a new active subscription.
    *   If the email exists but was unsubscribed: Reactivates the subscription.
    *   If the email exists and is active: Returns error (already subscribed).

    Args:
        website_id (str): The ID of the website.
        request (NewsletterSubscribeRequest): Email and optional name.

    Returns:
        NewsletterSubscriberResponse: Subscription details.
    """
    try:
        from second_brain_database.database import db_manager

        # Check if already subscribed
        existing = await db_manager.get_tenant_collection("blog_newsletter_subscribers").find_one(
            {"website_id": website_id, "email": request.email}
        )

        if existing:
            if existing.get("is_active"):
                raise HTTPException(status_code=400, detail="Already subscribed")
            else:
                # Reactivate subscription
                await db_manager.get_tenant_collection("blog_newsletter_subscribers").update_one(
                    {"_id": existing["_id"]}, {"$set": {"is_active": True, "unsubscribed_at": None}}
                )
                return NewsletterSubscriberResponse(**existing)

        # Create new subscription
        subscriber_doc = {
            "subscriber_id": f"subscriber_{uuid4().hex[:16]}",
            "website_id": website_id,
            "email": request.email,
            "name": request.name,
            "is_active": True,
            "subscribed_at": datetime.utcnow(),
        }

        await db_manager.get_tenant_collection("blog_newsletter_subscribers").insert_one(subscriber_doc)

        logger.info("New newsletter subscriber: %s for website %s", request.email, website_id)
        return NewsletterSubscriberResponse(**subscriber_doc)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to subscribe to newsletter: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to subscribe")


# Analytics tracking
@router.post("/analytics/track")
async def track_analytics(
    request: TrackAnalyticsRequest,
    req: Request = None,
):
    """
    Record a user engagement event (Analytics).

    This endpoint tracks interactions such as page views, likes, shares, and bookmarks.
    It is designed to be called by the frontend when these actions occur.

    **Privacy:**
    *   Logs IP address and User-Agent for unique visitor counting.
    *   Does NOT require authentication (tracks anonymous visitors).

    Args:
        request (TrackAnalyticsRequest): Event type and metadata.
        req (Request): The HTTP request object.

    Returns:
        dict: Success message.
    """
    try:
        from second_brain_database.database import db_manager

        # Get client info
        client_ip = req.client.host if req and req.client else "unknown"
        user_agent = req.headers.get("user-agent", "") if req else ""

        # Create analytics event
        event_doc = {
            "event_id": f"event_{uuid4().hex[:16]}",
            "event_type": request.event_type,
            "post_id": request.post_id,
            "referrer": request.referrer,
            "device_type": request.device_type or "unknown",
            "ip_address": client_ip,
            "user_agent": user_agent,
            "created_at": datetime.utcnow(),
        }

        await db_manager.get_tenant_collection("blog_analytics_events").insert_one(event_doc)

        # Update post counters
        if request.post_id:
            if request.event_type == "view":
                await db_manager.get_tenant_collection("blog_posts").update_one(
                    {"post_id": request.post_id}, {"$inc": {"view_count": 1}}
                )
            elif request.event_type == "like":
                await db_manager.get_tenant_collection("blog_posts").update_one(
                    {"post_id": request.post_id}, {"$inc": {"like_count": 1}}
                )

        return {"message": "Event tracked successfully"}

    except Exception as e:
        logger.error("Failed to track analytics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to track analytics")


@router.get("/websites/{website_id}/posts/{post_id}/engagement", response_model=EngagementMetricsResponse)
async def get_engagement_metrics(
    website_id: str,
    post_id: str,
    current_user: dict = Depends(require_access_viewer),
):
    """
    Retrieve aggregated engagement metrics for a post.

    Calculates total views, unique visitors, share counts, and other metrics
    based on the raw analytics events logged via `/analytics/track`.

    Args:
        website_id (str): The ID of the website.
        post_id (str): The ID of the post.
        current_user (dict): The authenticated user.

    Returns:
        EngagementMetricsResponse: Aggregated metrics.
    """
    try:
        # Access check handled by dependency

        from second_brain_database.database import db_manager

        # Get post
        post_doc = await db_manager.get_tenant_collection("blog_posts").find_one(
            {"post_id": post_id, "website_id": website_id}
        )

        if not post_doc:
            raise HTTPException(status_code=404, detail="Post not found")

        # Get analytics events
        total_views = 0
        unique_ips = set()
        shares = {"twitter": 0, "facebook": 0, "linkedin": 0}
        bookmarks = 0

        async for event in db_manager.get_tenant_collection("blog_analytics_events").find({"post_id": post_id}):
            if event["event_type"] == "view":
                total_views += 1
                unique_ips.add(event.get("ip_address", "unknown"))
            elif event["event_type"] == "share":
                platform = event.get("platform", "other")
                shares[platform] = shares.get(platform, 0) + 1
            elif event["event_type"] == "bookmark":
                bookmarks += 1

        return EngagementMetricsResponse(
            post_id=post_id,
            views=post_doc.get("view_count", 0),
            unique_views=len(unique_ips),
            avg_time_on_page=0.0,  # Would need session tracking
            bounce_rate=0.0,  # Would need session tracking
            shares=shares,
            bookmarks=bookmarks,
            comments=post_doc.get("comment_count", 0),
            likes=post_doc.get("like_count", 0),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get engagement metrics: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to get engagement metrics")
