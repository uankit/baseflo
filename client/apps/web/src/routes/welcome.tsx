import { createFileRoute, useNavigate } from '@tanstack/react-router';
import { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useGateway } from '../providers/GatewayProvider.js';

export const Route = createFileRoute('/welcome')({
  component: WelcomePage,
});

function WelcomePage() {
  const gateway = useGateway();
  const navigate = useNavigate();
  const [name, setName] = useState('');

  const projectsQuery = useQuery({
    queryKey: ['projects'],
    queryFn: () => gateway.projects.list(),
  });

  const createProject = useMutation({
    mutationFn: (n: string) => gateway.projects.create({ name: n }),
    onSuccess: (project) => {
      localStorage.setItem('baseflo_active_project', project.id);
      navigate({ to: '/p/$projectId', params: { projectId: project.id }, replace: true });
    },
  });

  if (projectsQuery.isSuccess && projectsQuery.data.length > 0) {
    const first = projectsQuery.data[0];
    if (first) {
      localStorage.setItem('baseflo_active_project', first.id);
      navigate({ to: '/p/$projectId', params: { projectId: first.id }, replace: true });
    }
    return null;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-950 px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight text-white">Welcome to Baseflo</h1>
          <p className="mt-2 text-sm text-gray-400">Create your first project to get started.</p>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            if (name.trim()) createProject.mutate(name.trim());
          }}
          className="space-y-4"
        >
          <input
            type="text"
            required
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-lg border border-gray-800 bg-gray-900 px-4 py-3 text-sm text-white placeholder-gray-500 outline-none focus:border-gray-600"
          />
          <button
            type="submit"
            disabled={createProject.isPending}
            className="w-full rounded-lg bg-white px-4 py-3 text-sm font-medium text-gray-950 hover:bg-gray-100 disabled:opacity-50"
          >
            {createProject.isPending ? 'Creating…' : 'Create Project'}
          </button>
        </form>
      </div>
    </div>
  );
}
