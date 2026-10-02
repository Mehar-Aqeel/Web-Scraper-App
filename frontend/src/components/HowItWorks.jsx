const STEPS = [
  {
    number: "01",
    title: "Enter a URL",
    description: "Paste any public website URL into the input field. Supports http and https.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244" />
      </svg>
    ),
  },
  {
    number: "02",
    title: "Choose Data Types",
    description: "Select what to extract — titles, headings, links, images, meta tags, Open Graph, tables, and more.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    number: "03",
    title: "Extract Data",
    description: "Click Extract Data. The backend fetches, parses, and returns structured results in milliseconds.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
      </svg>
    ),
  },
  {
    number: "04",
    title: "Filter & Export",
    description: "Search, filter by type, remove duplicates, then download as CSV, JSON, or Excel.",
    icon: (
      <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.8}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5M16.5 12L12 16.5m0 0L7.5 12m4.5 4.5V3" />
      </svg>
    ),
  },
];

const DATA_TYPES = [
  { label: "Page Title", color: "bg-blue-100 text-blue-700" },
  { label: "Headings (H1–H6)", color: "bg-purple-100 text-purple-700" },
  { label: "Links", color: "bg-green-100 text-green-700" },
  { label: "Images", color: "bg-yellow-100 text-yellow-700" },
  { label: "Meta Tags", color: "bg-pink-100 text-pink-700" },
  { label: "Open Graph", color: "bg-orange-100 text-orange-700" },
  { label: "Paragraphs", color: "bg-teal-100 text-teal-700" },
  { label: "Tables", color: "bg-indigo-100 text-indigo-700" },
  { label: "Canonical URL", color: "bg-red-100 text-red-700" },
];

const FEATURES = [
  {
    title: "SSRF Protected",
    description: "Private IPs and internal network addresses are blocked at the DNS level.",
    icon: "🛡️",
  },
  {
    title: "Robots.txt Aware",
    description: "Respects robots.txt disallow rules before fetching any page.",
    icon: "🤖",
  },
  {
    title: "JS Rendering",
    description: "Enable headless Playwright for JavaScript-heavy single-page apps.",
    icon: "⚡",
  },
  {
    title: "Batch Mode",
    description: "Extract from up to 20 URLs simultaneously in a single request.",
    icon: "📦",
  },
  {
    title: "Smart Filtering",
    description: "Filter by type, keyword search, hide empty values, and deduplicate rows.",
    icon: "🔍",
  },
  {
    title: "Multi-format Export",
    description: "Download your results as CSV, JSON, or Excel with one click.",
    icon: "📥",
  },
];

export default function HowItWorks({ onGetStarted }) {
  return (
    <section className="space-y-20 py-4">
      {/* Hero banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-blue-600 via-blue-700 to-indigo-800 px-8 py-16 text-center text-white shadow-xl">
        {/* Background decoration */}
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-0 left-1/4 w-72 h-72 rounded-full bg-white blur-3xl" />
          <div className="absolute bottom-0 right-1/4 w-72 h-72 rounded-full bg-indigo-300 blur-3xl" />
        </div>
        <div className="relative space-y-5">
          <span className="inline-block px-3 py-1 rounded-full bg-white/20 text-xs font-semibold uppercase tracking-widest">
            Universal Web Data Extractor
          </span>
          <h1 className="text-4xl sm:text-5xl font-extrabold tracking-tight">
            Extract Any Data<br />From Any Website
          </h1>
          <p className="max-w-xl mx-auto text-blue-100 text-lg leading-relaxed">
            Paste a URL, choose what to extract, and get structured data in seconds.
            No code required. Export to CSV, JSON, or Excel instantly.
          </p>
          <div className="flex flex-wrap justify-center gap-3 pt-2">
            <button
              onClick={onGetStarted}
              className="px-6 py-3 rounded-lg bg-white text-blue-700 font-semibold text-sm hover:bg-blue-50 transition-colors shadow focus:outline-none focus:ring-2 focus:ring-white"
            >
              Start Extracting →
            </button>
            <a
              href="#how-it-works"
              className="px-6 py-3 rounded-lg bg-white/10 text-white font-semibold text-sm hover:bg-white/20 transition-colors border border-white/20 focus:outline-none focus:ring-2 focus:ring-white"
            >
              See How It Works
            </a>
          </div>
        </div>
      </div>

      {/* Stats bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { value: "9+", label: "Data Types" },
          { value: "20x", label: "Batch URLs" },
          { value: "3", label: "Export Formats" },
          { value: "100%", label: "Free to Use" },
        ].map(({ value, label }) => (
          <div key={label} className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 text-center">
            <p className="text-3xl font-extrabold text-blue-600">{value}</p>
            <p className="text-sm text-gray-500 mt-1">{label}</p>
          </div>
        ))}
      </div>

      {/* How it works steps */}
      <div id="how-it-works" className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-gray-900">How It Works</h2>
          <p className="text-gray-500 text-sm max-w-md mx-auto">
            Four simple steps from URL to structured, exportable data.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
          {STEPS.map(({ number, title, description, icon }) => (
            <div key={number} className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4 hover:shadow-md transition-shadow">
              <div className="flex items-center justify-between">
                <div className="w-11 h-11 rounded-xl bg-blue-50 text-blue-600 flex items-center justify-center">
                  {icon}
                </div>
                <span className="text-3xl font-black text-gray-100">{number}</span>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 text-sm">{title}</h3>
                <p className="text-xs text-gray-500 mt-1 leading-relaxed">{description}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Supported data types */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 space-y-5">
        <div className="text-center space-y-1">
          <h2 className="text-2xl font-bold text-gray-900">Supported Data Types</h2>
          <p className="text-gray-500 text-sm">Everything you can extract from a single page.</p>
        </div>
        <div className="flex flex-wrap justify-center gap-2 pt-2">
          {DATA_TYPES.map(({ label, color }) => (
            <span key={label} className={`px-3 py-1.5 rounded-full text-xs font-semibold ${color}`}>
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Features grid */}
      <div className="space-y-6">
        <div className="text-center space-y-2">
          <h2 className="text-2xl font-bold text-gray-900">Built-in Safeguards & Features</h2>
          <p className="text-gray-500 text-sm max-w-md mx-auto">
            Production-grade protections and quality-of-life features out of the box.
          </p>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map(({ title, description, icon }) => (
            <div key={title} className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-2 hover:shadow-md transition-shadow">
              <div className="text-2xl">{icon}</div>
              <h3 className="font-semibold text-gray-900 text-sm">{title}</h3>
              <p className="text-xs text-gray-500 leading-relaxed">{description}</p>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="rounded-2xl bg-gray-900 text-white px-8 py-12 text-center space-y-4">
        <h2 className="text-2xl font-bold">Ready to extract some data?</h2>
        <p className="text-gray-400 text-sm max-w-sm mx-auto">
          No sign-up needed. Just paste a URL and go.
        </p>
        <button
          onClick={onGetStarted}
          className="mt-2 px-8 py-3 rounded-lg bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 transition-colors shadow focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          Open Extractor →
        </button>
      </div>
    </section>
  );
}
