/**
 * Footer - SQA Corporate Branding
 */
export default function Footer() {
  return (
    <footer className="bg-sqa-navy border-t border-sqa-border px-6 py-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-xl font-bold text-white">
            sqa<span className="text-sqa-gold">_</span>
          </span>
          <span className="text-lg text-slate-500">|</span>
          <span className="text-lg text-slate-400">
            Software Quality Assurance
          </span>
        </div>
        <div className="text-lg text-slate-500">
          JMeter Analyzer Pro v2.0 &copy; {new Date().getFullYear()}
        </div>
      </div>
    </footer>
  );
}
