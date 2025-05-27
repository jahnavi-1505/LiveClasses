import './globals.css';

export const metadata = { title: 'Live Classes', description: 'Schedule Zoom meetings' };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="p-8 font-sans" suppressHydrationWarning>
        <header className="mb-8">
          <h1 className="text-3xl font-bold">Live Classes</h1>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}