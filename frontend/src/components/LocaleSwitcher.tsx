"use client";

import { useLocale } from "next-intl";
import { useRouter, usePathname } from "../i18n/navigation";
import { locales, type Locale } from "../i18n/config";

const LABELS: Record<Locale, string> = {
  en: "EN",
  de: "DE",
};

export default function LocaleSwitcher() {
  const locale = useLocale() as Locale;
  const router = useRouter();
  const pathname = usePathname();

  function switchLocale(next: Locale) {
    if (next === locale) return;
    router.replace(pathname, { locale: next });
  }

  return (
    <div className="flex items-center gap-0.5" aria-label="Language">
      {locales.map((l) => (
        <button
          key={l}
          onClick={() => switchLocale(l)}
          className={`px-2 py-0.5 rounded text-xs font-semibold transition-colors ${
            l === locale
              ? "bg-blue-600 text-white"
              : "text-gray-500 dark:text-gray-400 hover:text-gray-800 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700"
          }`}
          aria-current={l === locale ? "true" : undefined}
        >
          {LABELS[l]}
        </button>
      ))}
    </div>
  );
}
