interface Props {
  children: React.ReactNode;
}

export default function PlayLayout({ children }: Props) {
  return <div className="play-layout">{children}</div>;
}
