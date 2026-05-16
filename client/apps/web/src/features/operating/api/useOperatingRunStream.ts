import { useCallback, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import type { RunEvent } from '@baseflo/api-client';
import { useGateway } from '../../../providers/GatewayProvider.js';
import { operatingKeys } from './queryKeys.js';
import {
  type OperatingRunStreamRequest,
  type OperatingRunStreamState,
  startOperatingRunWithEvents,
} from './runStream.js';

const initialState: OperatingRunStreamState = {
  runId: null,
  status: 'idle',
  events: [],
  result: null,
  error: null,
};

export function useOperatingRunStream() {
  const gateway = useGateway();
  const queryClient = useQueryClient();
  const [state, setState] = useState<OperatingRunStreamState>(initialState);

  const start = useCallback(
    async (request: OperatingRunStreamRequest) => {
      setState({ ...initialState, status: 'starting' });
      try {
        const result = await startOperatingRunWithEvents(gateway, request, (event: RunEvent) => {
          const isFailedEvent = event.type === 'operating.failed' || event.type === 'run.failed';
          setState((current) => ({
            ...current,
            runId: event.run_id,
            status: isFailedEvent ? 'failed' : 'running',
            events: [...current.events, event],
          }));
        });
        setState((current) => ({
          ...current,
          runId: result.run_id,
          status: result.status,
          result,
          error: null,
        }));
        await queryClient.invalidateQueries({ queryKey: operatingKeys.all });
        return result;
      } catch (error) {
        const normalized = error instanceof Error ? error : new Error(String(error));
        setState((current) => ({
          ...current,
          status: 'failed',
          error: normalized,
        }));
        throw normalized;
      }
    },
    [gateway, queryClient],
  );

  return {
    ...state,
    start,
    isRunning: state.status === 'starting' || state.status === 'running',
    reset: () => setState(initialState),
  };
}
