import { Icon } from "@iconify-icon/react";
import { Tooltip } from "../ui/tooltip";

type tQuestionMark = {
  message?: string;
};

export const QuestionMark = ({ message }: tQuestionMark) => {
  if (!message) return null;

  return (
    <Tooltip content={message} enabled>
      <span className="text-custom-blue-50 border border-sm rounded-full w-4 h-4 flex items-center justify-center cursor-pointer">
        <Icon icon={"mdi:question-mark"} className="text-xxs" />
      </span>
    </Tooltip>
  );
};
