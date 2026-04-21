import { z } from 'zod';
import { ClaimVerdictSchema } from './claim';

/**
 * Normalized scenario run — produced by an adapter from a raw JSON.
 * `raw` is preserved unparsed so scenario-specific features can dig deeper
 * without forcing the common type to grow.
 */
export const ScenarioRunSchema = z.object({
  scenario: z.string(),
  timestamp: z.string(),
  models: z.array(z.string()),
  claims: z.array(ClaimVerdictSchema),
  adr: z.string().optional(),
  raw: z.unknown(),
});
export type ScenarioRun = z.infer<typeof ScenarioRunSchema>;
