'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, Server, Settings, AlertCircle } from 'lucide-react';

interface NavItem {
    name: string;
    href: string;
    icon: React.ReactNode;
}

const navigation: NavItem[] = [
    { name: 'Overview', href: '/', icon: <Home size={20} /> },
    { name: 'Nodes', href: '/nodes', icon: <Server size={20} /> },
    { name: 'Alerts', href: '/alerts', icon: <AlertCircle size={20} /> },
    { name: 'Settings', href: '/settings', icon: <Settings size={20} /> },
];

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();

    return (
        <div className="min-h-screen bg-gray-900 text-white">
            {/* Header */}
            <header className="bg-gray-800 border-b border-gray-700">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
                    <div className="flex justify-between items-center">
                        <div>
                            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                                SBD Cluster
                            </h1>
                            <p className="text-sm text-gray-400 mt-1">Distributed Database Management</p>
                        </div>
                        <div className="flex items-center gap-2">
                            <div className="h-2 w-2 bg-green-400 rounded-full animate-pulse"></div>
                            <span className="text-sm text-gray-400">Connected</span>
                        </div>
                    </div>
                </div>
            </header>

            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <div className="flex gap-8">
                    {/* Sidebar */}
                    <aside className="w-64 shrink-0">
                        <nav className="space-y-1">
                            {navigation.map((item) => {
                                const isActive = pathname === item.href;
                                return (
                                    <Link
                                        key={item.name}
                                        href={item.href}
                                        className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${isActive
                                                ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                                                : 'text-gray-400 hover:bg-gray-800 hover:text-white'
                                            }`}
                                    >
                                        {item.icon}
                                        <span className="font-medium">{item.name}</span>
                                    </Link>
                                );
                            })}
                        </nav>
                    </aside>

                    {/* Main Content */}
                    <main className="flex-1 min-w-0">
                        <React.Suspense
                            fallback={
                                <div className="flex items-center justify-center h-64">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
                                </div>
                            }
                        >
                            {children}
                        </React.Suspense>
                    </main>
                </div>
            </div>
        </div>
    );
}
