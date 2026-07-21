interface Props {
  children: React.ReactNode;
  className?: string;
}

export default function PlayLayout({ children, className = "" }: Props) {
  return <div className={`play-layout ${className}`.trim()}>{children}</div>;
}
