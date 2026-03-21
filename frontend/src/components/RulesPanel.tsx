"use client";

import { useTranslations } from "next-intl";

export default function RulesPanel() {
  const t = useTranslations("rulesPanel");

  return (
    <details className="rounded-lg border border-gray-200 overflow-hidden text-sm">
      <summary className="px-4 py-2 cursor-pointer font-medium text-gray-600 hover:bg-gray-50 select-none list-none flex items-center gap-2">
        <span className="text-base">ℹ</span> {t("toggle")}
      </summary>
      <div className="px-4 py-3 space-y-3 text-gray-600 bg-gray-50 border-t border-gray-200">

        <div>
          <p className="font-semibold text-gray-700">{t("run")}</p>
          <p dangerouslySetInnerHTML={{ __html: t("runDesc") }} />
          <p className="text-xs text-gray-400 mt-0.5">{t("runExample")}</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700">{t("group")}</p>
          <p dangerouslySetInnerHTML={{ __html: t("groupDesc") }} />
          <p className="text-xs text-gray-400 mt-0.5">{t("groupExample")}</p>
        </div>

        <div>
          <p className="font-semibold text-gray-700">{t("firstTurn")}</p>
          <p dangerouslySetInnerHTML={{ __html: t("firstTurnDesc") }} />
        </div>

        <div>
          <p className="font-semibold text-gray-700">{t("joker")}</p>
          <p>{t("jokerDesc")}</p>
        </div>

      </div>
    </details>
  );
}
