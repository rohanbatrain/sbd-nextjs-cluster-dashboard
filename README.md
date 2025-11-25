# Second Brain Database

![banner](https://github.com/user-attachments/assets/85429929-ac86-4a03-8cd7-4e473d4fd402)

[![Docker Dev Test](https://github.com/rohanbatrain/second_brain_database/workflows/Docker%20Dev%20Test/badge.svg)](https://github.com/rohanbatrain/second_brain_database/actions/workflows/docker-test-dev.yml)
[![Docker Test Suite](https://github.com/rohanbatrain/second_brain_database/workflows/Docker%20Test%20Suite/badge.svg)](https://github.com/rohanbatrain/second_brain_database/actions/workflows/docker-test-test.yml)
[![Docker Production Build](https://github.com/rohanbatrain/second_brain_database/workflows/Docker%20Production%20Build/badge.svg)](https://github.com/rohanbatrain/second_brain_database/actions/workflows/docker-build-prod.yml)

**A Centralized Approach to Personal Knowledge Management**

Welcome to the **Second Brain Database**! This project is a culmination of years of learning, experimentation, and refinement in the world of personal knowledge management (PKM). After working with several tools like Notion, Obsidian, Todoist, and others, I've developed a flexible and platform-independent system that centralizes data without tying you to a single tool.

## � Introduction

**Second Brain Database** is designed to help you organize and centralize your personal knowledge, tasks, and thoughts in a flexible, platform-agnostic way. It empowers you to adapt your system over time without the burden of platform dependency.

## � Key Features

- **Flexibility**: You’re not locked into any one platform or tool. Migrate and switch between different platforms while keeping your data consistent.
- **Centralized Data**: All your data is stored in a consistent and structured manner, no matter which frontend or tool you choose to interact with.
- **Modular Micro Frontends**: Small, task-focused frontends like *Emotion Capture* help you work on specific tasks without unnecessary features.
- **Open-Source**: This project is open for everyone. It’s about sharing and collaborating to improve personal knowledge management for all.

## 🔑 My Philosophy: Flexibility Without Compromise

The core philosophy behind Second Brain Database is simple: centralize your data, but never let platform dependency limit your flexibility. Traditional tools like Obsidian store data in a markdown-based format but rely heavily on platform-specific plugins. The moment you switch platforms, all that data becomes fragmented and loses its value.

Second Brain Database resolves this by using **MongoDB** to store data in a non-structured, platform-agnostic way. Whether you are using Flask v1, v2, or v3, the data remains consistent and usable across all tools.

## 🧠 Micro Frontends: Solving Complex Problems Simply

The project incorporates micro frontends to keep things modular and focused. For example, the *Emotion Capture* frontend is designed specifically to capture and store emotions without overwhelming you with other features. These small, focused frontends operate independently, interacting with the centralized MongoDB database via the Flask API.

## 📦 Project Status

Second Brain Database is **still under active development**. The core functionality is in place, and a beta release is coming soon. Once the beta is ready, I'll provide more details on how you can try it out and contribute to its development.

## 🐳 Docker Quick Start

The easiest way to run Second Brain Database is with Docker Compose:

```bash
# 1. Clone the repository
git clone https://github.com/rohanbatrain/second_brain_database.git
cd second_brain_database

# 2. Copy environment file
cp .env.development.example .env

# 3. Start all services
cd infra
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 4. Access the API
open http://localhost:8000/docs
```

**Or use the Makefile:**

```bash
make docker-up
```

For comprehensive Docker documentation, see [docs/DOCKER.md](docs/DOCKER.md).

### Docker Pull

```bash
docker pull rohanbatra/second_brain_database:latest
```


## 🌍 Open-Source for the Community

I believe in the power of collaboration, so this project is open-source. It’s not just for me—it's for anyone who’s looking for a more adaptable, flexible approach to personal knowledge management. By releasing it to the community, I hope to receive contributions that will make it even better for everyone.

## 🚀 Why You Should Try Second Brain Database

- **Flexibility**: Easily migrate your data and switch platforms without losing consistency.
- **Centralized Data**: Keep your data organized, regardless of the tool you use to interact with it.
- **Modular Micro Frontends**: Focus on specific tasks without unnecessary complexity.
- **Open Source**: Contribute to the project and help it evolve over time.

## 🙏 Thank You for Your Support

This journey has been long, and I’m thrilled to share this tool with you. I hope Second Brain Database can help you organize your thoughts, tasks, and knowledge in a way that gives you the freedom to explore new productivity systems without being restricted by them.

Stay tuned for the upcoming beta release announcement. If you’re ready to explore, learn, or contribute, check out the project on GitHub. Together, we can make it even better!


Let’s build smarter, more adaptable systems for managing our thoughts and data. 🚀

---

### Technologies Used
- **FastAPI**: Modern, high-performance Python web framework for building APIs
- **MongoDB**: For centralized, platform-agnostic data storage
- **Redis**: For caching, session management, and Celery message broker
- **Qdrant**: Vector database for RAG (Retrieval-Augmented Generation) capabilities
- **Celery**: Distributed task queue for async processing
- **Docker**: Containerization for easy deployment and development
- **Micro Frontends**: Modular frontends for specific tasks and ease of use