import type { ElementType } from 'react';
import { Link } from '@tanstack/react-router';
import {
  IconCustomers,
  IconProducts,
  IconOrders,
  IconAnalytics,
  IconLayers,
} from '@baseflo/ui/icons';
import type { BusinessEntityView } from '../model/schemas.js';
import { labelize } from '../../common/model/format.js';

const ENTITY_ICONS: Record<string, ElementType> = {
  customer: IconCustomers,
  customers: IconCustomers,
  product: IconProducts,
  products: IconProducts,
  order: IconOrders,
  orders: IconOrders,
  invoice: IconAnalytics,
  invoices: IconAnalytics,
  vendor: IconLayers,
  vendors: IconLayers,
  supplier: IconLayers,
  suppliers: IconLayers,
};

export function EntityCard({ entity }: { entity: BusinessEntityView }) {
  const Icon = ENTITY_ICONS[entity.entity.toLowerCase()] ?? IconLayers;
  return (
    <div className="flex flex-col border border-ink/20 bg-paper-soft p-4 shadow-[2px_2px_0_rgba(28,25,20,0.08)]">
      <div className="flex items-center gap-3">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center border border-ink/15 bg-paper">
          <Icon className="h-4 w-4 text-ink/55" />
        </div>
        <div>
          <h3 className="text-sm font-bold text-ink">{labelize(entity.plural)}</h3>
          <p className="text-xs text-ink/50">{entity.description}</p>
        </div>
      </div>
      {entity.suggested_questions.length ? (
        <div className="mt-3 space-y-1">
          {entity.suggested_questions.slice(0, 2).map((q) => (
            <Link
              key={q}
              to="/workspace/ask"
              search={{ q }}
              className="block truncate text-xs leading-5 text-ink/60 hover:text-flame"
            >
              {q}
            </Link>
          ))}
        </div>
      ) : null}
      <p className="mt-3 border-t border-ink/10 pt-2 text-[11px] leading-4 text-ink/40">
        {entity.source_asset_ids.length} source{entity.source_asset_ids.length > 1 ? 's' : ''}
      </p>
    </div>
  );
}
