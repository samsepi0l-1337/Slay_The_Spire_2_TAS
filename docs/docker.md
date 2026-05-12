# Docker

## Build

macOS, Linux, Windows PowerShell 모두 같은 이미지 이름을 사용합니다.

```bash
docker build -t sts2-tas:local .
docker run --rm sts2-tas:local --help
```

## Windows PowerShell

Docker Desktop에서 Linux containers 모드를 사용합니다. 현재 프로젝트 폴더를 `/workspace`로 mount하고, 입력 screenshot과 JSONL/model 파일은 volume 안에서 읽고 씁니다.

```powershell
docker build -t sts2-tas:local .
docker run --rm -v "${PWD}:/workspace" sts2-tas:local --help
```

예시:

```powershell
docker run --rm -v "${PWD}:/workspace" sts2-tas:local capture `
  --screenshot data/reward.png `
  --out data/snapshots.jsonl `
  --game-version 0.105.1 `
  --branch beta `
  --character ironclad `
  --ascension 0 `
  --floor 1 `
  --deck strike,bash `
  --relics burning_blood `
  --hp 70 `
  --gold 99
```

## Runtime Boundary

The container runs the CLI and model code. It does not capture the Windows desktop or click the game window. For v1, capture screenshots on the host and pass those files into the container through a volume.

Generated datasets and models should stay outside the image:

- `data/*.jsonl`
- `data/*.png`
- `models/*.joblib`
