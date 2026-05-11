import { createRouter } from '@tanstack/react-router';
import { routeTree } from './routeTree.gen.js';
import type { Gateway } from '@baseflo/api-client';

export interface RouterContext {
  gateway: Gateway;
}

export const router = createRouter({
  routeTree,
  context: { gateway: undefined! },
  defaultPreload: 'intent',
  defaultPreloadStaleTime: 30_000,
});
