import { useNavigate } from "react-router-dom";
import { selectAuthUser } from "@/app/store/authSlice";
import { useAppSelector } from "@/app/store/hooks";
import { MasterIcon } from "@/components/navigation/icons";
import { visibleMasterStages } from "@/config/navigation";
import { masterStageIcons } from "@/modules/master/masterStageIcons";
import { ModuleStageMenu } from "./ModuleStageMenu";

type MasterMenuProps = {
  onClose: () => void;
};

export function MasterMenu({ onClose }: MasterMenuProps) {
  const navigate = useNavigate();
  const user = useAppSelector(selectAuthUser);

  return (
    <ModuleStageMenu
      title="Master"
      subtitle="Select a master to continue"
      badgeIcon={<MasterIcon />}
      stages={visibleMasterStages(user)}
      icons={masterStageIcons}
      onClose={onClose}
      searchable
      searchPlaceholder="Search masters..."
      onSelect={(stage) => {
        if (stage.to) {
          navigate(stage.to);
          onClose();
        }
      }}
    />
  );
}
