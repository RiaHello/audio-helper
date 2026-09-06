export default function CitySelect({ value, onChange }) {
  return (
    <label className="field">
      <span>所在城市</span>
      <input
        type="text"
        name="city"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        autoComplete="off"
      />
    </label>
  );
}
