import { useEffect, useState } from "react";
import { useFormContext } from "react-hook-form";
import { OpsCodeEditor } from "../../components/form/code-editor";
import OpsCheckbox from "../../components/form/checkbox";
import { OpsColorPicker } from "../../components/form/color-picker";
import { OpsDatePicker } from "../../components/form/date-picker";
import { OpsInput } from "../../components/form/input";
import OpsList from "../../components/form/list";
import { OpsSelect } from "../../components/form/select";
import { OpsSelect2Step } from "../../components/form/select-2-step";
import OpsSwitch from "../../components/form/switch";
import { OpsTextarea } from "../../components/form/textarea";
import { DynamicFieldData } from "./dynamic-control-types";

export const DynamicControl = (props: DynamicFieldData) => {
  const {
    type,
    name,
    value,
    options = {
      values: [],
    },
    parent,
    config,
  } = props;

  const { setValue, getValues, register } = useFormContext();

  if (type === "checkbox") {
    register(name, {
      value,
      ...config,
    });
  } else {
    register(name, {
      value: value || "",
      ...config,
    });
  }

  // Initial state to reuse user value or value from props if not defined
  const [localValue, setLocalValue] = useState(getValues(name) && !value ? getValues(name) : value);

  const handleChange = (newValue: any) => {
    setLocalValue(newValue);
    setValue(name, newValue);
  };

  useEffect(() => {
    // Handle value change if parent updates it
    if (!value) return;

    handleChange(value);
  }, [value]);

  switch (type) {
    case "password":
    case "text":
    case "number":
      return <OpsInput {...props} value={localValue} onChange={handleChange} />;
    case "textarea":
      return <OpsTextarea {...props} value={localValue} onChange={handleChange} />;
    case "switch":
      return <OpsSwitch {...props} value={localValue} onChange={handleChange} />;
    case "checkbox":
      return <OpsCheckbox {...props} value={localValue} onChange={handleChange} />;
    case "select":
      return <OpsSelect {...props} value={localValue} onChange={handleChange} />;
    case "dropdown": {
      return <OpsSelect {...props} value={localValue} onChange={handleChange} dropdown />;
    }
    case "enum": {
      return <OpsSelect {...props} value={localValue} onChange={handleChange} enum />;
    }
    case "select2step": {
      const selectOptions = Array.isArray(options)
        ? options.map((o) => ({
            name: o.name,
            id: o.id,
          }))
        : [];

      const selectValue = parent
        ? {
            parent,
            child: value,
          }
        : {
            parent: null,
            child: null,
          }; // Initial value msut be empty if not defined

      return (
        <OpsSelect2Step
          {...props}
          options={selectOptions}
          value={selectValue}
          onChange={(newOption) => {
            setLocalValue(newOption.child);
            setValue(name, newOption.child);
          }}
        />
      );
    }
    case "multiselect": {
      return <OpsSelect {...props} value={localValue} onChange={handleChange} multiple />;
    }
    case "list": {
      return <OpsList {...props} value={localValue} onChange={handleChange} />;
    }
    case "datepicker": {
      return <OpsDatePicker {...props} value={localValue} onChange={handleChange} />;
    }
    case "json": {
      return (
        <OpsCodeEditor
          {...props}
          value={localValue}
          onChange={(value: string) => {
            // Set the JSON as string in state
            setLocalValue(value);

            if (!value) {
              // Replace empty string with valid "null"
              setValue(name, null);
            }

            try {
              // Store the value as JSON
              const newValue = JSON.parse(value);
              setValue(name, newValue);
            } catch (e) {
              console.log("Error while saving new value: ", e);
            }
          }}
        />
      );
    }
    case "color": {
      return <OpsColorPicker {...props} value={localValue} onChange={handleChange} />;
    }
    default:
      return null;
  }
};
