import { NextResponse } from "next/server";
import { readdir, readFile } from "fs/promises";
import { join } from "path";

const OUTPUT_DIR = "/Users/enderj/EkoContentStudio/output";

export async function GET() {
  try {
    const files = await readdir(OUTPUT_DIR);
    const pipelineFiles = files
      .filter((f) => f.startsWith("pipeline_") && f.endsWith(".json"))
      .sort()
      .reverse();

    const pipelines = await Promise.all(
      pipelineFiles.slice(0, 30).map(async (f) => {
        try {
          const raw = await readFile(join(OUTPUT_DIR, f), "utf-8");
          const data = JSON.parse(raw);

          // Pass through compact stage summary that includes arrays so the UI
          // can infer status when the `status` field is missing.
          const stages: Record<string, any> = {};
          for (const [k, v] of Object.entries(data.stages || {})) {
            const stage = v as any;
            stages[k] = {
              status: stage?.status,
              scripts: stage?.scripts?.length
                ? new Array(stage.scripts.length)
                : undefined,
              produced: stage?.produced?.length
                ? new Array(stage.produced.length)
                : undefined,
              uploaded: stage?.uploaded?.length
                ? new Array(stage.uploaded.length)
                : undefined,
              published: stage?.published?.length
                ? new Array(stage.published.length)
                : undefined,
            };
          }

          return {
            filename: f,
            started_at: data.started_at,
            business_name: data.business_name,
            stages,
            paperclip_issue_id: data.paperclip_issue_id,
          };
        } catch {
          return null;
        }
      })
    );

    return NextResponse.json({
      pipelines: pipelines.filter(Boolean),
    });
  } catch (err: any) {
    return NextResponse.json(
      { error: err.message || "Failed to load pipelines" },
      { status: 500 }
    );
  }
}
