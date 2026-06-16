import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listModelPolicies, ModelPolicy, upsertModelPolicy } from "@/api/modelPolicies";

const PROVIDER_OPTIONS = [
  { value: "mock", label: "Mock（本地规则，无需 API Key）" },
  { value: "openai_compat", label: "OpenAI 兼容（/v1/chat/completions）" },
];

const SCENE_CONFIG: Record<
  string,
  { title: string; description: string; defaultModel: string; saveLabel: string }
> = {
  chat: {
    title: "对话场景（chat）",
    description: "学生工作台右侧聊天（总规划 / 学科智能体）。",
    defaultModel: "mock-v1",
    saveLabel: "保存 chat 策略",
  },
  paper_gen: {
    title: "组卷场景（paper_gen）",
    description: "学生自测卷 AI 组卷；未配置或生成失败时自动降级为规则卷。",
    defaultModel: "gpt-4.1-mini",
    saveLabel: "保存 paper_gen 策略",
  },
  grading: {
    title: "批改场景（grading）",
    description: "自测卷主观题 AI 批改与评语；客观题仍按标准答案判分。未配置时使用 mock。",
    defaultModel: "gpt-4.1-mini",
    saveLabel: "保存 grading 策略",
  },
};

function paramsToText(params: Record<string, unknown>): string {
  return JSON.stringify(params ?? {}, null, 2);
}

function parseParamsText(raw: string): Record<string, unknown> {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed) as unknown;
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("params 必须是 JSON 对象");
  }
  return parsed as Record<string, unknown>;
}

function OpenAiParamsHint() {
  return (
    <p className="text-xs text-slate-500 mt-2 leading-relaxed">
      可选在 params 中填写 <code className="bg-slate-100 px-1 rounded">base_url</code>、
      <code className="bg-slate-100 px-1 rounded">api_key</code>；也可在服务端设置环境变量{" "}
      <code className="bg-slate-100 px-1 rounded">AIT_LLM_BASE_URL</code>、
      <code className="bg-slate-100 px-1 rounded">AIT_LLM_API_KEY</code>。
      阿里云 MaaS 示例 base_url：
      <code className="bg-slate-100 px-1 rounded block mt-1">
        https://你的实例.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
      </code>
      模型名需与控制台一致（如 qwen-plus）。
    </p>
  );
}

function ScenePolicyForm({
  scene,
  policy,
  isLoading,
}: {
  scene: string;
  policy?: ModelPolicy;
  isLoading: boolean;
}) {
  const qc = useQueryClient();
  const config = SCENE_CONFIG[scene];
  const syncedPolicyKey = useRef<string | null>(null);

  const [provider, setProvider] = useState("mock");
  const [model, setModel] = useState(config.defaultModel);
  const [paramsText, setParamsText] = useState("{}");
  const [paramsError, setParamsError] = useState<string | null>(null);

  const policyKey = policy
    ? `${policy.id}:${policy.provider}:${policy.model}:${paramsToText(policy.params)}`
    : null;

  useEffect(() => {
    if (!policy || !policyKey) return;
    if (syncedPolicyKey.current === policyKey) return;
    syncedPolicyKey.current = policyKey;
    setProvider(policy.provider);
    setModel(policy.model);
    setParamsText(paramsToText(policy.params));
    setParamsError(null);
  }, [policy, policyKey]);

  const saveMut = useMutation({
    mutationFn: () => {
      const params = parseParamsText(paramsText);
      return upsertModelPolicy(scene, { scene, provider, model, params });
    },
    onSuccess: () => {
      syncedPolicyKey.current = null;
      qc.invalidateQueries({ queryKey: ["admin", "model-policies"] });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    setParamsError(null);
    try {
      parseParamsText(paramsText);
    } catch (err) {
      setParamsError((err as Error).message);
      return;
    }
    saveMut.mutate();
  };

  return (
    <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 space-y-4">
      <div>
        <h2 className="font-medium text-slate-800">{config.title}</h2>
        <p className="text-sm text-slate-600 mt-1">{config.description}</p>
      </div>

      <label className="block">
        <span className="text-sm text-slate-600">Provider</span>
        <select
          className="mt-1 border rounded px-3 py-2 w-full"
          value={provider}
          onChange={(e) => setProvider(e.target.value)}
        >
          {PROVIDER_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </label>

      <label className="block">
        <span className="text-sm text-slate-600">Model</span>
        <input
          className="mt-1 border rounded px-3 py-2 w-full"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          placeholder={provider === "mock" ? config.defaultModel : "gpt-4.1-mini"}
          required
        />
      </label>

      <label className="block">
        <span className="text-sm text-slate-600">Params（JSON）</span>
        <textarea
          className="mt-1 border rounded px-3 py-2 w-full font-mono text-sm min-h-[100px]"
          value={paramsText}
          onChange={(e) => {
            setParamsText(e.target.value);
            setParamsError(null);
          }}
          spellCheck={false}
        />
        {provider === "openai_compat" && <OpenAiParamsHint />}
        {paramsError && (
          <p role="alert" className="text-red-600 text-sm mt-1">
            {paramsError}
          </p>
        )}
      </label>

      <button
        type="submit"
        disabled={saveMut.isPending || isLoading}
        className="bg-slate-900 text-white rounded py-2 px-4 disabled:opacity-50"
      >
        {saveMut.isPending ? "保存中…" : config.saveLabel}
      </button>
      {saveMut.isSuccess && <p className="text-green-700 text-sm">已保存。</p>}
      {saveMut.error && (
        <p role="alert" className="text-red-600 text-sm">
          {(saveMut.error as Error).message}
        </p>
      )}
      {!isLoading && !policy && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
          尚未配置 {scene} 策略，将使用默认 mock / 规则降级。
        </p>
      )}
    </form>
  );
}

export default function ModelPolicies() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "model-policies"],
    queryFn: listModelPolicies,
  });

  const otherPolicies = (data ?? []).filter(
    (p) => !Object.prototype.hasOwnProperty.call(SCENE_CONFIG, p.scene),
  );

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">模型策略</h1>
        <p className="text-sm text-slate-600 mt-1">
          按场景配置本机构使用的大模型。保存后立即对学生端生效。
        </p>
        {error && (
          <p role="alert" className="text-red-600 text-sm mt-2">
            {(error as Error).message}
          </p>
        )}
        {isLoading && <p className="text-slate-500 text-sm mt-2">加载策略中…</p>}
      </div>

      <ScenePolicyForm
        scene="chat"
        policy={data?.find((p) => p.scene === "chat")}
        isLoading={isLoading}
      />
      <ScenePolicyForm
        scene="paper_gen"
        policy={data?.find((p) => p.scene === "paper_gen")}
        isLoading={isLoading}
      />
      <ScenePolicyForm
        scene="grading"
        policy={data?.find((p) => p.scene === "grading")}
        isLoading={isLoading}
      />

      {otherPolicies.length > 0 && (
        <section className="bg-white shadow rounded">
          <h2 className="px-4 py-3 font-medium border-b text-slate-800">其他场景</h2>
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="px-4 py-2">场景</th>
                <th className="px-4 py-2">Provider</th>
                <th className="px-4 py-2">Model</th>
              </tr>
            </thead>
            <tbody>
              {otherPolicies.map((p) => (
                <tr key={p.id} className="border-t">
                  <td className="px-4 py-2 font-mono">{p.scene}</td>
                  <td className="px-4 py-2">{p.provider}</td>
                  <td className="px-4 py-2">{p.model}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="px-4 py-2 text-xs text-slate-500">
            以上场景之外的历史策略，仅展示不可在此页编辑。
          </p>
        </section>
      )}
    </div>
  );
}
