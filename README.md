# sbd-nextjs-cluster-dashboard

The **Cluster Dashboard** provides real-time monitoring and management for the Second Brain Database cluster. It visualizes node status, health metrics, and system performance.

## Features

-   **Cluster Overview**: View the status of all nodes in the cluster.
-   **Real-time Metrics**: Monitor CPU, memory, and network usage.
-   **Node Management**: detailed view of individual node performance.
-   **Alerts**: Visual indicators for system issues.

## Tech Stack

-   **Framework**: [Next.js 16](https://nextjs.org/)
-   **Language**: TypeScript
-   **Styling**: [Tailwind CSS 4](https://tailwindcss.com/)
-   **Data Fetching**: SWR
-   **Visualization**: Recharts
-   **Animations**: Framer Motion

## Prerequisites

-   Node.js 20+
-   pnpm (recommended) or npm/yarn

## Getting Started

1.  **Install dependencies**:
    ```bash
    pnpm install
    ```

2.  **Run the development server**:
    ```bash
    pnpm dev
    ```
    Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Scripts

-   `pnpm dev`: Run the development server.
-   `pnpm build`: Build the application for production.
-   `pnpm start`: Start the production server.
-   `pnpm lint`: Run ESLint.

## License

Private
