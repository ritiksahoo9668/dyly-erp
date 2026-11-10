import type { ModuleOverviewConfig } from "@/modules/shared/ModuleOverview";

/** Builds a submodule overview from a parent module config using the same template. */
export function createSubmoduleOverviewConfig(
  parent: ModuleOverviewConfig,
  submodule: { title: string; description: string },
): ModuleOverviewConfig {
  return {
    ...parent,
    title: submodule.title,
    description: submodule.description,
  };
}
