export default function Footer() {
  return (
    <footer className="bg-gray-900 text-gray-400 mt-20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-10">
          {/* Brand */}
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-md bg-blue-600 flex items-center justify-center">
                <svg className="w-3.5 h-3.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
              </div>
              <span className="text-white font-bold text-base">
                Web<span className="text-blue-400">Extractor</span>
              </span>
            </div>
            <p className="text-sm leading-relaxed">
              A universal web data extraction tool. Scrape titles, headings, links, images, meta tags, and more from any public URL.
            </p>
          </div>

          {/* Features */}
          <div>
            <h3 className="text-white text-sm font-semibold mb-4 uppercase tracking-wider">Features</h3>
            <ul className="space-y-2 text-sm">
              {["HTML Extraction", "JS Rendering (Playwright)", "Batch URL Mode", "CSV / JSON / Excel Export", "Scraping History", "Rate Limiting & SSRF Protection"].map((f) => (
                <li key={f} className="flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-blue-500 shrink-0" />
                  {f}
                </li>
              ))}
            </ul>
          </div>

          {/* Tech stack */}
          <div>
            <h3 className="text-white text-sm font-semibold mb-4 uppercase tracking-wider">Built With</h3>
            <ul className="space-y-2 text-sm">
              {[
                { name: "FastAPI", desc: "Python backend" },
                { name: "React + Vite", desc: "Frontend" },
                { name: "Tailwind CSS", desc: "Styling" },
                { name: "Playwright", desc: "JS rendering" },
                { name: "BeautifulSoup4", desc: "HTML parsing" },
                { name: "Pandas", desc: "CSV export" },
              ].map(({ name, desc }) => (
                <li key={name} className="flex items-center justify-between">
                  <span className="text-gray-300 font-medium">{name}</span>
                  <span className="text-xs text-gray-500">{desc}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>

        <div className="mt-10 pt-6 border-t border-gray-800 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs">
          <p>© {new Date().getFullYear()} WebExtractor. Built for portfolio purposes.</p>
          <div className="flex items-center gap-1 text-gray-500">
            <span className="w-2 h-2 rounded-full bg-green-500 inline-block" />
            All systems operational
          </div>
        </div>
      </div>
    </footer>
  );
}
