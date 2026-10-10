/** Quiet placeholder for a backend route that is not deployed yet. */
export default function ComingSoon({ what }: { what: string }) {
  return (
    <p data-testid="soon" className="text-body-md text-on-surface-variant bg-surface-container rounded-[12px] px-space-md py-space-sm">
      {what}: Disponible pronto
    </p>
  );
}
