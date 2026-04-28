import Layout from '@/components/Layout';

export default function Home() {
  return (
    <Layout>
      <div className="text-center py-12">
        <h1 className="text-4xl font-bold mb-4 text-primary">Welcome to the NGO Volunteer Platform</h1>
        <p className="text-lg text-foreground opacity-80 mb-8 max-w-2xl mx-auto">
          Connect community needs with skilled volunteers.
        </p>
        <div className="flex justify-center space-x-4">
          <a href="/login" className="bg-primary text-primary-foreground px-6 py-3 rounded-lg hover:opacity-90 font-medium transition-opacity">
            Login
          </a>
          <a href="/register" className="bg-secondary text-secondary-foreground px-6 py-3 rounded-lg hover:opacity-90 font-medium transition-opacity">
            Register
          </a>
        </div>
      </div>
    </Layout>
  );
}
