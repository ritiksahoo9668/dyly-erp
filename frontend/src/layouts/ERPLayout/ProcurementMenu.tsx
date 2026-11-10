import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import {
  StageCsIcon,
  StageGateIcon,
  StageGrnIcon,
  StageIndentIcon,
  StagePlanningIcon,
  StagePoIcon,
  StageQcIcon,
  StageRfqIcon,
  StageWeighIcon,
} from "@/components/navigation/icons";
import { procurementStages, visibleStages } from "@/config/navigation";
import { ModuleStageMenu } from "./ModuleStageMenu";

const stageIcons = {
  planning: StagePlanningIcon,
  indent: StageIndentIcon,
  rfq: StageRfqIcon,
  cs: StageCsIcon,
  po: StagePoIcon,
  "gate-entry": StageGateIcon,
  weighbridge: StageWeighIcon,
  qc: StageQcIcon,
  grn: StageGrnIcon,
};

type ProcurementMenuProps = {
  onClose: () => void;
};

export function ProcurementMenu({ onClose }: ProcurementMenuProps) {
  const user = useAppSelector(selectAuthUser);

  return (
    <ModuleStageMenu
      title="Procurement"
      subtitle="Select a stage to continue"
      badgeIcon={<StagePoIcon />}
      stages={visibleStages(user, "procurement", procurementStages)}
      icons={stageIcons}
      onClose={onClose}
    />
  );
}
