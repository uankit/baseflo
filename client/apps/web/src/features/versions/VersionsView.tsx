import { useNavigate, useParams } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import {
  Button,
  Card,
  CardContent,
  EmptyState,
  ErrorCallout,
  LoadingSkeletonRow,
  ValidationBadge,
  useToast,
} from '@baseflo/ui';
import { useGateway } from '../../providers/GatewayProvider.js';

export function VersionsView() {
  const params = useParams({
    from: '/o/$orgSlug/p/$projectSlug/v/$versionId',
  });
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();

  const projectQuery = useQuery({
    queryKey: ['project', params.orgSlug, params.projectSlug],
    queryFn: () => gateway.projects.get(params.orgSlug, params.projectSlug),
  });
  const projectId = projectQuery.data?.id ?? null;

  const versionsQuery = useQuery({
    queryKey: ['versions', projectId],
    queryFn: () => gateway.projects.versions(projectId!),
    enabled: !!projectId,
  });

  const rollback = useMutation({
    mutationFn: (versionId: string) => gateway.projects.rollback(projectId!, versionId),
    onSuccess: ({ currentVersionId }) => {
      toast.push({ title: 'Rolled back', variant: 'success' });
      queryClient.invalidateQueries({ queryKey: ['versions', projectId] });
      navigate({
        to: '/o/$orgSlug/p/$projectSlug/v/$versionId',
        params: { ...params, versionId: currentVersionId },
      });
    },
  });

  return (
    <div className="flex flex-col gap-4">
      <header>
        <h1 className="text-xl font-semibold text-fg">Versions</h1>
        <p className="text-sm text-fg-muted">
          Every refinement creates an immutable version. Roll back at any time.
        </p>
      </header>
      <Card>
        <CardContent className="p-0">
          {versionsQuery.isPending ? (
            <div className="flex flex-col">
              {[0, 1, 2].map((i) => (
                <LoadingSkeletonRow key={i} />
              ))}
            </div>
          ) : versionsQuery.isError ? (
            <ErrorCallout title="Couldn't load versions" message="Try again." />
          ) : versionsQuery.data.length === 0 ? (
            <EmptyState title="No versions yet" />
          ) : (
            <ul className="divide-y divide-border">
              {versionsQuery.data.map((v) => {
                const isCurrent = v.id === params.versionId;
                return (
                  <li
                    key={v.id}
                    className="flex items-center justify-between gap-4 p-4"
                  >
                    <div className="flex items-center gap-4">
                      <span className="font-mono text-sm font-medium tabular-nums">
                        v{v.versionNumber}
                      </span>
                      <ValidationBadge status={v.validationStatus} />
                      <span className="text-xs text-fg-muted">
                        {format(new Date(v.createdAt), 'MMM d, yyyy h:mm a')}
                      </span>
                      {isCurrent && (
                        <span className="text-xs font-medium text-accent">Current</span>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() =>
                          navigate({
                            to: '/o/$orgSlug/p/$projectSlug/v/$versionId',
                            params: { ...params, versionId: v.id },
                          })
                        }
                      >
                        View
                      </Button>
                      {!isCurrent && (
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={rollback.isPending}
                          onClick={() => rollback.mutate(v.id)}
                        >
                          Roll back
                        </Button>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
