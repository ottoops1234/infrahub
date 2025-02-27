import { LockClosedIcon } from "@heroicons/react/24/outline";
import { FormFieldError } from "../../screens/edit-form-hook/form";
import { classNames } from "../../utils/common";
import { QuestionMark } from "../display/question-mark";
import { ColorPicker } from "../inputs/color-picker";

type OpsColorPickerProps = {
  label: string;
  description?: string;
  value: string;
  onChange: (value: string) => void;
  className?: string;
  error?: FormFieldError;
  isProtected?: boolean;
  isOptional?: boolean;
  isUnique?: boolean;
  disabled?: boolean;
};

export const OpsColorPicker = (props: OpsColorPickerProps) => {
  const {
    className,
    onChange,
    value,
    label,
    description,
    error,
    isProtected,
    isOptional,
    disabled,
  } = props;

  return (
    <>
      <div className="flex items-center gap-1.5">
        <label htmlFor={label} className="text-sm font-medium leading-6 text-gray-900">
          {label} {!isOptional && "*"}
        </label>
        {isProtected && <LockClosedIcon className="w-4 h-4" />}
        <QuestionMark message={description} />
      </div>
      <ColorPicker
        onChange={onChange}
        defaultValue={value ?? ""}
        className={classNames(className ?? "")}
        error={error}
        disabled={isProtected || disabled}
      />
    </>
  );
};
