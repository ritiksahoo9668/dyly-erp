import { useNavigate } from "react-router-dom";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import {
  SalesIcon,
  StageDeliveryOrderIcon,
  StageDispatchIcon,
  StageGateExitIcon,
  StageGateIcon,
  StageInquiryIcon,
  StageInvoiceIcon,
  StageOfferIcon,
  StagePlanningIcon,
  StagePoIcon,
} from "@/components/navigation/icons";
import { salesStages, visibleStages } from "@/config/navigation";
import { ModuleStageMenu } from "./ModuleStageMenu";

const stageIcons = {
  planning: StagePlanningIcon,
  "inquiry-capture": StageInquiryIcon,
  "sales-offer": StageOfferIcon,
  "po-received": StagePoIcon,
  do: StageDeliveryOrderIcon,
  "gate-entry": StageGateIcon,
  "dispatch-loading": StageDispatchIcon,
  invoice: StageInvoiceIcon,
  "gate-exit": StageGateExitIcon,
};

type SalesMenuProps = {
  onClose: () => void;
};

export function SalesMenu({ onClose }: SalesMenuProps) {
  const navigate = useNavigate();
  const user = useAppSelector(selectAuthUser);

  return (
    <ModuleStageMenu
      title="Sales"
      subtitle="Select a stage to continue"
      badgeIcon={<SalesIcon />}
      stages={visibleStages(user, "sales", salesStages)}
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
