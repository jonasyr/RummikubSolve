"use client";

import { useTranslations } from "next-intl";

const bold = (chunks: React.ReactNode) => (
  <strong className="font-semibold text-gray-800 dark:text-gray-200">{chunks}</strong>
);

export default function RulesPanel() {
  const t = useTranslations("rulesPanel");

  return (
    <details className="rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden text-sm">
      <summary className="px-4 py-2 cursor-pointer font-medium text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-800 select-none list-none flex items-center gap-2">
        <span className="text-base">ℹ</span> {t("toggle")}
      </summary>
      <div className="px-4 py-3 space-y-3 text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">

        <div>
          <p className="font-semibold text-gray-700 dark:text-gray-300">{t("run")}</p>
          <p>{t.rich("runDesc", { strong: bold })}</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{t("runExample")}</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700 dark:text-gray-300">{t("group")}</p>
          <p>{t.rich("groupDesc", { strong: bold })}</p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{t("groupExample")}</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700 dark:text-gray-300">{t("firstTurn")}</p>
          <p>{t.rich("firstTurnDesc", { strong: bold })}</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700 dark:text-gray-300">{t("joker")}</p>
          <p>{t("jokerDesc")}</p>
        </div>

      </div>
    </details>
  );
}
