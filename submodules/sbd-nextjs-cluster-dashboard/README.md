# SBD Cluster Dashboard - Production Deployment

The cluster management dashboard for monitoring and managing your distributed SBD deployment.

## 🚀 Quick Start

### Development

```bash
# Install dependencies
npm install

# Set environment variables
cp .env.example .env.local
# Edit .env.local with your backend URL

# Run development server
npm run dev
```

Visit `http://localhost:3000`

### Production Build

```bash
# Build for production
npm run build

# Start production server
npm start
```

## ⚙️ Configuration

Create `.env.production`:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-sbd-backend.com
```

## 🐳 Docker Deployment

### Build Image

```bash
docker build -t sbd-cluster-dashboard .
```

### Run Container

```bash
docker run -p 3000:3000 \
  -e NEXT_PUBLIC_API_BASE_URL=https://your-sbd-backend.com \
  sbd-cluster-dashboard
```

## ☸️ Kubernetes Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sbd-cluster-dashboard
spec:
  replicas: 2
  selector:
    matchLabels:
      app: sbd-dashboard
  template:
    metadata:
      labels:
        app: sbd-dashboard
    spec:
      containers:
      - name: dashboard
        image: sbd-cluster-dashboard:latest
        ports:
        - containerPort: 3000
        env:
        - name: NEXT_PUBLIC_API_BASE_URL
          value: "http://sbd-backend-service:8000"
---
apiVersion: v1
kind: Service
metadata:
  name: sbd-dashboard-service
spec:
  selector:
    app: sbd-dashboard
  ports:
  - port: 80
    targetPort: 3000
  type: LoadBalancer
```

## 📚 Features

- **Real-time Monitoring**: Auto-refreshing cluster health metrics
- **Node Management**: View, promote, demote nodes
- **Alerts System**: Real-time alerts with resolve functionality
- **Settings**: Configure cluster parameters
- **Responsive Design**: Works on desktop, tablet, and mobile
- **Dark Mode**: Easy on the eyes

## 🔧 Tech Stack

- **Framework**: Next.js 15
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Charts**: Recharts
- **Icons**: Lucide React

## 📖 Usage

### Dashboard Overview
- View cluster health summary
- Monitor replication lag
- Track pending events
- See recent alerts

### Nodes Page
- List all cluster nodes
- View node details and metrics
- Promote/demote nodes
- Remove nodes from cluster

### Alerts Page
- View active alerts sorted by severity
- Resolve alerts
- Filter by severity or node
- View alert history

### Settings
- Configure alert thresholds
- Update cluster parameters
- View cluster configuration

## 🔒 Security

This dashboard is designed for **owner-only access**. In production:

1. Deploy behind authentication (OAuth, JWT, etc.)
2. Use HTTPS for all connections
3. Restrict network access to authorized IPs
4. Enable CORS only for trusted domains

## 🐛 Troubleshooting

**Dashboard shows "Failed to load"**:
- Check `NEXT_PUBLIC_API_BASE_URL` is set correctly
- Verify backend is running and accessible
- Check browser console for CORS errors

**Alerts not updating**:
- Auto-refresh interval is 10 seconds
- Check backend `/cluster/alerts/active` endpoint

**Slow performance**:
- Reduce refresh intervals in `src/lib/api.ts`
- Enable caching in production build
- Use CDN for static assets

## 📄 License

Same as main SBD project
