import { useNavigate } from "react-router-dom";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import {
  ProductionIcon,
  StageFeedIcon,
  StagePlanningIcon,
  StageProductionEntryIcon,
} from "@/components/navigation/icons";
import { productionStages, visibleStages } from "@/config/navigation";
import { ModuleStageMenu } from "./ModuleStageMenu";

const stageIcons = {
  planning: StagePlanningIcon,
  "feed-consumption": StageFeedIcon,
  "production-entry": StageProductionEntryIcon,
};

type ProductionMenuProps = {
  onClose: () => void;
};

export function ProductionMenu({ onClose }: ProductionMenuProps) {
  const navigate = useNavigate();
  const user = useAppSelector(selectAuthUser);

  return (
    <ModuleStageMenu
      title="Production"
      subtitle="Select a stage to continue"
      badgeIcon={<ProductionIcon />}
      stages={visibleStages(user, "production", productionStages)}
      icons={stageIcons}
      onClose={onClose}
      onSelect={(stage) => {
        if (stage.to) {
          navigate(stage.to);
          onClose();
        }
      }}
    />
  );
}
