import { Link } from '@tanstack/react-router';
import { Button } from '@/components/ui/button';

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center p-8">
      <div className="text-center">
        <h1 className="text-6xl font-bold text-gray-900 dark:text-gray-100">404</h1>
        <p className="mt-4 text-xl text-gray-600 dark:text-gray-400">
          Page not found
        </p>
        <p className="mt-2 text-gray-500 dark:text-gray-500">
          The page you're looking for doesn't exist.
        </p>
        <div className="mt-8">
          <Link to="/">
            <Button>
              Go back home
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
