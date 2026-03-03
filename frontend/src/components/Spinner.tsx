export function Spinner({ size = 24 }: { size?: number }) {
  return (
    <div
      className="spinner"
      style={{
        width: size,
        height: size,
        borderWidth: Math.max(2, size / 8) + 'px'
      }}
    />
  )
}
