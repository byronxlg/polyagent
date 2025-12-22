import { Link } from '@tanstack/react-router';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

interface ResourceNotFoundProps {
  resourceType: string;
  resourceId: number | string;
}

export function ResourceNotFound({ resourceType, resourceId }: ResourceNotFoundProps) {
  return (
    <div className="flex h-full items-center justify-center p-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <div className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            <CardTitle>Resource Not Found</CardTitle>
          </div>
          <CardDescription>
            The {resourceType} you're looking for doesn't exist
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {resourceType.charAt(0).toUpperCase() + resourceType.slice(1)} #{resourceId} could not be found.
          </p>
          <Link to="/">
            <Button className="w-full">
              Return to Home
            </Button>
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
