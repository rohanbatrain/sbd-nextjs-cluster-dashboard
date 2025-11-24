'use client';

import React from 'react';
import DashboardLayout from '@/components/layout/DashboardLayout';
import { useClusterHealth } from '@/lib/api';
import { Activity, Server, Database, AlertTriangle, CheckCircle, Clock } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';

const data = [
  { name: '00:00', events: 400, lag: 24 },
  { name: '04:00', events: 300, lag: 13 },
  { name: '08:00', events: 200, lag: 98 },
  { name: '12:00', events: 278, lag: 39 },
  { name: '16:00', events: 189, lag: 48 },
  { name: '20:00', events: 239, lag: 38 },
  { name: '24:00', events: 349, lag: 43 },
];

export default function Home() {
  const { health, isLoading, isError } = useClusterHealth();

  if (isLoading) return (
    <DashboardLayout>
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
    </DashboardLayout>
  );

  if (isError) return (
    <DashboardLayout>
      <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400">
        Failed to load cluster health data. Is the backend running?
      </div>
    </DashboardLayout>
  );

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <StatCard
            title="Total Nodes"
            value={health?.total_nodes || 0}
            icon={<Server className="text-blue-400" />}
            trend="+1 this week"
          />
          <StatCard
            title="Healthy Nodes"
            value={health?.healthy_nodes || 0}
            icon={<CheckCircle className="text-green-400" />}
            subValue={`${health?.unhealthy_nodes || 0} unhealthy`}
          />
          <StatCard
            title="Replication Lag"
            value={`${(health?.avg_replication_lag || 0).toFixed(3)}s`}
            icon={<Clock className="text-yellow-400" />}
            trend="Avg across replicas"
          />
          <StatCard
            title="Pending Events"
            value={health?.total_events_pending || 0}
            icon={<Database className="text-purple-400" />}
            subValue={`${health?.total_events_failed || 0} failed`}
          />
        </div>

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
            <h3 className="text-lg font-medium mb-4">Replication Throughput</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="colorEvents" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }}
                    itemStyle={{ color: '#e5e7eb' }}
                  />
                  <Area type="monotone" dataKey="events" stroke="#3b82f6" fillOpacity={1} fill="url(#colorEvents)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
            <h3 className="text-lg font-medium mb-4">Replication Lag</h3>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data}>
                  <defs>
                    <linearGradient id="colorLag" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#f59e0b" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#f59e0b" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="name" stroke="#9ca3af" />
                  <YAxis stroke="#9ca3af" />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151' }}
                    itemStyle={{ color: '#e5e7eb' }}
                  />
                  <Area type="monotone" dataKey="lag" stroke="#f59e0b" fillOpacity={1} fill="url(#colorLag)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
          <div className="p-6 border-b border-gray-700 flex justify-between items-center">
            <h3 className="text-lg font-medium">System Alerts</h3>
            <button className="text-sm text-blue-400 hover:text-blue-300">View All</button>
          </div>
          <div className="divide-y divide-gray-700">
            {health?.unhealthy_nodes > 0 && (
              <div className="p-4 flex items-start gap-4 bg-red-500/5">
                <AlertTriangle className="text-red-400 shrink-0 mt-1" size={20} />
                <div>
                  <h4 className="font-medium text-red-400">Unhealthy Nodes Detected</h4>
                  <p className="text-sm text-gray-400 mt-1">
                    {health.unhealthy_nodes} nodes are reporting unhealthy status. Check node logs for details.
                  </p>
                  <p className="text-xs text-gray-500 mt-2">Just now</p>
                </div>
              </div>
            )}
            <div className="p-4 flex items-start gap-4">
              <CheckCircle className="text-green-400 shrink-0 mt-1" size={20} />
              <div>
                <h4 className="font-medium text-green-400">Cluster Rebalanced</h4>
                <p className="text-sm text-gray-400 mt-1">
                  Automatic load balancing successfully redistributed connections across 3 nodes.
                </p>
                <p className="text-xs text-gray-500 mt-2">2 hours ago</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}

function StatCard({ title, value, icon, subValue, trend }: any) {
  return (
    <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
      <div className="flex justify-between items-start mb-4">
        <div className="p-2 bg-gray-700/50 rounded-lg">
          {icon}
        </div>
        {trend && <span className="text-xs text-gray-400">{trend}</span>}
      </div>
      <h3 className="text-gray-400 text-sm font-medium">{title}</h3>
      <div className="flex items-baseline gap-2 mt-1">
        <p className="text-2xl font-bold text-white">{value}</p>
        {subValue && <span className="text-xs text-gray-500">{subValue}</span>}
      </div>
    </div>
  );
}
