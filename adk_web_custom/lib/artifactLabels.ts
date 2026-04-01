/**
 * 아티팩트 이름 → 한글 라벨 매핑
 * 매핑이 없으면 원래 이름을 그대로 반환합니다.
 *
 * 값을 추가하려면 아래 객체에 { "artifact_name": "한글 이름" } 형태로 넣으세요.
 */
const ARTIFACT_LABEL_MAP: Record<string, string> = {
  // 예시 (실제 값은 여기에 추가)
  // "dataset.csv": "데이터셋",
  // "result.csv": "분석 결과",
  // "report.pdf": "보고서",
};

/**
 * 아티팩트 이름을 한글 라벨로 변환합니다.
 * 매핑이 없으면 원래 이름을 반환합니다.
 */
export function getArtifactLabel(name: string): string {
  return ARTIFACT_LABEL_MAP[name] ?? name;
}
