/** The centred column shared by the sign-in and demo entry pages (SCREEN_SPECIFICATIONS S-01). */
export function AuthLayout({ children, showForm = true }: { children?: React.ReactNode; showForm?: boolean }) {
  return (
    <main id="content" className="flex min-h-dvh flex-col items-center px-4 py-12 sm:py-16">
      <div className="flex w-full max-w-[400px] flex-col gap-6">
        <div className="flex flex-col gap-1 text-center">
          <p className="text-title-lg">RetailOps Intelligence</p>
          <p className="text-body text-muted-foreground">Turn operational chaos into clear decisions.</p>
        </div>
        {showForm ? children : null}
        <footer className="text-center text-xs font-normal text-muted-foreground">
          An independent portfolio project by Lê Văn Trung Tính ·{" "}
          <a href="https://trungtinh.site" className="text-link underline underline-offset-2">
            trungtinh.site
          </a>
        </footer>
      </div>
    </main>
  );
}
