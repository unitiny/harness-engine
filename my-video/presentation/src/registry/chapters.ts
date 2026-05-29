import type { ChapterDef } from "./types";
import HookChapter from "../chapters/01-hook/Hook";
import { narrations as hookNarrations } from "../chapters/01-hook/narrations";
import DevHarnessChapter from "../chapters/02-dev-harness/DevHarness";
import { narrations as devHarnessNarrations } from "../chapters/02-dev-harness/narrations";
import MetaHarnessChapter from "../chapters/03-meta-harness/MetaHarness";
import { narrations as metaHarnessNarrations } from "../chapters/03-meta-harness/narrations";
import SelfEvolveChapter from "../chapters/04-self-evolve/SelfEvolve";
import { narrations as selfEvolveNarrations } from "../chapters/04-self-evolve/narrations";

export const CHAPTERS: ChapterDef[] = [
  {
    id: "hook",
    title: "为什么需要 harness",
    narrations: hookNarrations,
    Component: HookChapter,
  },
  {
    id: "dev-harness",
    title: "Dev Harness：执行层",
    narrations: devHarnessNarrations,
    Component: DevHarnessChapter,
  },
  {
    id: "meta-harness",
    title: "Meta Harness：观测层",
    narrations: metaHarnessNarrations,
    Component: MetaHarnessChapter,
  },
  {
    id: "self-evolve",
    title: "自进化闭环",
    narrations: selfEvolveNarrations,
    Component: SelfEvolveChapter,
  },
];
