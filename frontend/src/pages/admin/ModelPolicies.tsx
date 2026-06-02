import { FormEvent, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { listModelPolicies, upsertModelPolicy } from "@/api/modelPolicies";

const CHAT_SCENE = "chat";

const PROVIDER_OPTIONS = [
  { value: "mock", label: "Mock（本地规则，无需 API Key）" },
  { value: "openai_compat", label: "OpenAI 兼容（/v1/chat/completions）" },
];

const DEFAULT_CHAT: Omit<ModelPolicy, "id" | "org_id"> = {
  scene: CHAT_SCENE,
  provider: "mock",
  model: "mock-v1",
  params: {},
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

export default function ModelPolicies() {
  const qc = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["admin", "model-policies"],
    queryFn: listModelPolicies,
  });

  const [provider, setProvider] = useState(DEFAULT_CHAT.provider);
  const [model, setModel] = useState(DEFAULT_CHAT.model);
  const [paramsText, setParamsText] = useState(paramsToText(DEFAULT_CHAT.params));
  const [paramsError, setParamsError] = useState<string | null>(null);
  const syncedPolicyKey = useRef<string | null>(null);

  const chatPolicy = data?.find((p) => p.scene === CHAT_SCENE);
  const chatPolicyKey = chatPolicy
    ? `${chatPolicy.id}:${chatPolicy.provider}:${chatPolicy.model}:${paramsToText(chatPolicy.params)}`
    : null;

  useEffect(() => {
    if (!chatPolicy || !chatPolicyKey) return;
    if (syncedPolicyKey.current === chatPolicyKey) return;
    syncedPolicyKey.current = chatPolicyKey;
    setProvider(chatPolicy.provider);
    setModel(chatPolicy.model);
    setParamsText(paramsToText(chatPolicy.params));
    setParamsError(null);
  }, [chatPolicy, chatPolicyKey]);

  const saveMut = useMutation({
    mutationFn: () => {
      const params = parseParamsText(paramsText);
      return upsertModelPolicy(CHAT_SCENE, {
        scene: CHAT_SCENE,
        provider,
        model,
        params,
      });
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

  const otherPolicies = (data ?? []).filter((p) => p.scene !== CHAT_SCENE);

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h1 className="text-xl font-semibold">模型策略</h1>
        <p className="text-sm text-slate-600 mt-1">
          配置学生端聊天智能体（总规划 / 学科）使用的模型。保存后立即对本机构所有学生会话生效。
        </p>
      </div>

      <form onSubmit={onSubmit} className="bg-white shadow rounded p-4 space-y-4">
        <h2 className="font-medium text-slate-800">对话场景（chat）</h2>

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
            placeholder={provider === "mock" ? "mock-v1" : "gpt-4.1-mini"}
            required
          />
        </label>

        <label className="block">
          <span className="text-sm text-slate-600">Params（JSON）</span>
          <textarea
            className="mt-1 border rounded px-3 py-2 w-full font-mono text-sm min-h-[120px]"
            value={paramsText}
            onChange={(e) => {
              setParamsText(e.target.value);
              setParamsError(null);
            }}
            spellCheck={false}
          />
          {provider === "openai_compat" && (
            <p className="text-xs text-slate-500 mt-2 leading-relaxed">
              可选在 params 中填写 <code className="bg-slate-100 px-1 rounded">base_url</code>、
              <code className="bg-slate-100 px-1 rounded">api_key</code>；也可在服务端设置环境变量{" "}
              <code className="bg-slate-100 px-1 rounded">AIT_LLM_BASE_URL</code>、
              <code className="bg-slate-100 px-1 rounded">AIT_LLM_API_KEY</code>（优先于 params）。
              示例：{" "}
              <code className="bg-slate-100 px-1 rounded block mt-1 whitespace-pre-wrap">
                {`{\n  "base_url": "https://api.openai.com",\n  "api_key": "sk-..."\n}`}
              </code>
            </p>
          )}
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
          {saveMut.isPending ? "保存中…" : "保存 chat 策略"}
        </button>
        {saveMut.isSuccess && (
          <p className="text-green-700 text-sm">已保存。</p>
        )}
        {saveMut.error && (
          <p role="alert" className="text-red-600 text-sm">
            {(saveMut.error as Error).message}
          </p>
        )}
        {error && (
          <p role="alert" className="text-red-600 text-sm">
            {(error as Error).message}
          </p>
        )}
      </form>

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
            当前页面仅支持编辑 chat；grading 等场景请通过 API 配置。
          </p>
        </section>
      )}

      {isLoading && <p className="text-slate-500 text-sm">加载策略中…</p>}
      {!isLoading && !chatPolicy && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
          尚未配置 chat 策略，学生聊天将使用默认 mock。填写上方表单并保存即可。
        </p>
      )}
    </div>
  );
}
