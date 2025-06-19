import './globals.css';
import Link from 'next/link';

export const metadata = {
  title: 'Live Classes',
  description: 'Schedule Zoom meetings',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body suppressHydrationWarning>
        <nav className="bg-primary text-white p-4 shadow-md">
          <div className="container flex justify-between items-center">
            <Link href="/" className="text-2xl font-bold">
              Live Classes
            </Link>
            <div className="space-x-4">
              <Link href="/" className="hover:text-secondary">
                Sessions
              </Link>
            </div>
          </div>
        </nav>
        <main className="container mt-8 mb-12">
          {children}
        </main>
      </body>
    </html>
  );
}