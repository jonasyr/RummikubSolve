"use client";

import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { usePlayStore } from "../../store/play";

export default function ControlBar() {
  const t = useTranslations("play");
  const locale = useLocale();

  const past = usePlayStore((s) => s.past);
  const future = usePlayStore((s) => s.future);
  const showValidation = usePlayStore((s) => s.showValidation);
  const undo = usePlayStore((s) => s.undo);
  const redo = usePlayStore((s) => s.redo);
  const commit = usePlayStore((s) => s.commit);
  const revert = usePlayStore((s) => s.revert);
  const toggleValidation = usePlayStore((s) => s.toggleValidation);

  const btnBase =
    "h-11 px-3 rounded text-sm font-medium border border-gray-300 dark:border-gray-600 " +
    "hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div className="flex flex-wrap items-center gap-2">
      <Link
        href={`/${locale}`}
        className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
      >
        {t("nav.toSolver")}
      </Link>

      <div className="flex gap-1">
        <button
          className={btnBase}
          onClick={undo}
          disabled={past.length === 0}
        >
          {t("undo")}
        </button>
        <button
          className={btnBase}
          onClick={redo}
          disabled={future.length === 0}
        >
          {t("redo")}
        </button>
      </div>

      <div className="flex gap-1 ml-auto">
        <button className={btnBase} onClick={toggleValidation}>
          {showValidation ? t("hideValidation") : t("showValidation")}
        </button>
        <button
          className="h-11 px-3 rounded text-sm font-medium bg-blue-600 text-white hover:bg-blue-700"
          onClick={() => {
            commit();
          }}
        >
          {t("commit")}
        </button>
        <button className={btnBase} onClick={revert}>
          {t("revert")}
        </button>
      </div>
    </div>
  );
}
