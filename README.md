# VRM RETRO VIEWER

- 公開：https://haruka-apps-games.itch.io/vrm-retro-viewer（itch.io、無料の HTML5 ツール）
- 記事：https://qiita.com/haruka_apps/items/29b897418b601cfacb6c

VRM（0.x / 1.0）を開くと、Pyxel 3 のレトロな 3D で表示するビューアです。231 種類のモーション（CC0）で動かせて、2D ゲーム用のスプライトシート（PNG と GIF）や、Pyxel 3 用の 3D データを zip で書き出せます。

- ファイルはどこにも送りません。読み込みも変換も、ブラウザ（または自分の PC）の中だけで行います。
- ツール本体は itch.io の HTML5 ツールです（`os`・`js` などを使うので、ツール本体は Code & Magic では動きません）。書き出した Pyxel 用 3D データは Code & Magic でも動きます。

## 動かし方

### ブラウザ（itch.io と同じ形）

```
cd web
python3 -m http.server
```

ブラウザで http://localhost:8000 を開きます。初回は Pyodide と numpy・Pillow の読み込みに時間がかかります。

itch.io には `vrm_viewer_itch.zip`（index.html・vrm_viewer.pyxapp・sample.vrm の 3 ファイル）をアップロードします。

### デスクトップ

```
python main.py                 # ウィンドウに VRM をドロップ
python main.py avatar.vrm      # ファイルを直接開く
```

## クレジット

- Pyxel 3：Takashi Kitao（MIT License）https://github.com/kitao/pyxel
- ブラウザ版で使っているもの：Pyodide（MPL-2.0）、NumPy（BSD-3-Clause）、Pillow（MIT-CMU）
- モーション：Quaternius「Universal Animation Library」1・2（CC0）、Kay Lousberg「KayKit Character Animations」（CC0）。open-vrma プロジェクトによる .vrma 変換
- サンプルアバター：千駄ヶ谷 渋（VRoid の CC0 サンプルモデル、軽量化して同梱）
- ツール：haruka_apps（main.py・vrm_io.py・vrm_figure.py・サンプルは MIT）

## 免責

本ツールと、本ツールで書き出したファイルは「現状のまま（AS IS）」提供します。動作や結果について、いかなる保証もしません。利用によって生じたいかなる損害・トラブルについても、作者（haruka_apps）は一切責任を負いません。読み込む VRM のライセンスを守るのは利用者の責任です。

## 画面（ブラウザ）

- 「Try sample」：同梱のサンプルアバター（千駄ヶ谷 渋、約 4 MB）を読み込みます。押したときだけダウンロードします

- 上のバー：Open VRM、モーション選択、T-pose、Reset view、Screenshot、GIF
- 右のパネル：アバター名・作者・ライセンス（URL はクリックできます）・警告、書き出し設定
- スマホ幅では、パネルは画面の下に移ります
- 画面のドラッグで回転、ホイールで拡大縮小

## キー

| キー | 動作 |
|---|---|
| ← → / ↑ ↓ | 回す / 近づく・離れる |
| SPACE | 次のモーション |
| T | T ポーズ |
| E | 標準設定でスプライトを書き出し（idle / walk / run / jump / punch / hit / death） |
| D | Pyxel 用 3D を書き出し |
| P / G | スクリーンショット / GIF |
| L | ライセンス表示の入 / 切（デスクトップ） |
| F1 | 処理時間の表示 |

## ライセンスの表示

VRM に書かれた利用条件（meta）を表示します。改変禁止・再配布禁止・作者のみ利用可などのときは赤い警告を出します（書き出しは止めません）。書き出した zip の README.txt と sheet.json にも、元の VRM の利用条件を書き込みます。

## 書き出し（`<名前>_sprites.zip`）

設定：1 マスの大きさ（32〜128 px）、向き（8 または 4）、コマ数（4〜12）、モーション。

| ファイル | 中身 |
|---|---|
| `<名前>_<モーション>.png` | 1 モーション 1 枚。行 = 向き、列 = コマ |
| `<名前>_<モーション>.gif` | 正面（下向き）のアニメーション GIF（2 倍の大きさ） |
| `<名前>_all.png` | 全モーションを縦に積んだ 1 枚。高さが 8192 px 以下のとき（少なめの書き出し）だけ作ります |
| `sheet.json` | マスの大きさ、向きの順、モーションごとのファイル・コマ数・fps・ループ・`_all.png` での y 位置、`palette`（全 PNG が使う 256 色） |
| `README.txt` | 上の説明と、元 VRM の利用条件 |
| `pyxel_sample/sample_sprites.py` | Pyxel のサンプル（任意。`pyxel run pyxel_sample/sample_sprites.py`）。Python を使わない人は無視してかまいません |
| `pyxel_sample/HOW_TO_RUN.txt` | サンプルの動かし方（Windows / Mac、英語と日本語） |

- 向きの順（8 方向）：下、左下、左、左上、上、右上、右、右下。4 方向：下、左、上、右
- 背景は透明です。透明な部分の色はマゼンタ（0xFF00FF）にしてあるので、Pyxel ではカラーキーとして使えます。ほかのツールではふつうの透明 PNG として読めます
- GIF の背景も透明です

サンプルの操作：矢印で歩く（8 方向）、X で走る、Z で攻撃（punch・sword・spell のうち書き出したもの）。

## Pyxel 用 3D の書き出し（`<名前>_pyxel3d.zip`）

変換したアバター（色を 239 色に減らし、テクスチャを 256 px に縮めたもの）を、Pyxel 3 のゲームでそのまま使える形で書き出します。

| ファイル | 中身 |
|---|---|
| `model.tmx` | メッシュ、骨、ウェイト、パレット、元 VRM の情報（numpy の npz を base64 の文字にしたもの） |
| `tex_*.png` | テクスチャ（パレットの色だけで描いたもの） |
| `motions.tmx` | 231 モーション（同じく base64、約 2.8 MB） |
| `vrm_figure.py` | 読み込みと再生のコード（pyxel・numpy・json・base64・io だけ。os / sys なし） |
| `sample_3d.py` | 床の上を歩かせるサンプル（`pyxel run sample_3d.py`） |
| `README.txt` / `HOW_TO_RUN.txt` | 使い方、元 VRM の利用条件、免責 / 動かし方（英語と日本語） |

```python
from vrm_figure import Figure
fig = Figure("folder/")      # pyxel.cube の Node
stage.add_child(fig)
fig.play("walk")
fig.animate(1 / 30)          # 毎フレーム
```

- `.tmx` にしているのは、Code & Magic にアップロードできる形式（.py / .png / .tmx / .glb / .ogg / .pyxres）に合わせるためです。中身は 1×1 の Tiled のマップで、property "data" に npz を base64 で入れています（base64 の文字だけでは C&M に「中身が .tmx と一致しません」と断られます）
- C&M では、全ファイルを上げて sample_3d.py を main.py に名前を変えます
- パレットの 16〜255 番を使います（255 = マゼンタのカラーキー）。0〜15 番はゲーム側の色のままです
- 書き出し中は、ボタンが押せなくなり、進み具合（%）が出ます

## モーション（231 本、すべて CC0）

| グループ | 本数 | 中身 |
|---|---:|---|
| Basic | 15 | idle, walk, run, sprint, jump, punch, sword, spell, hit, death, roll, crouch, talk, dance, ninja_jump（サンプルが使う短い名前） |
| Quaternius | 64 | Universal Animation Library 1・2 の残り（剣のコンボ、銃、農作業、泳ぎ、ゾンビなど） |
| KayKit | 125 | KayKit Character Animations（Rig_Medium）。名前の頭に `kk_` |
| KayKit Large | 27 | 同じく Rig_Large。名前の頭に `kkl_` |

- 出典：Quaternius「Universal Animation Library」1・2（CC0）、Kay Lousberg「KayKit Character Animations」（CC0）。open-vrma プロジェクトが .vrma に変換したもの（Mac の `vrm_motion_lib/vrma_cc0/`）を使っています。同じ場所の CMU は CC0 ではない（販売不可）ので入れていません
- 外したもの：変身テスト 2 本、地面の下や空中から現れる出現モーション 5 本、1 m よじ登り（スプライトのマスからはみ出すため）
- KayKit は元のキャラが太めなので、腕が体から大きく離れています。焼くときに両腕を 28 度下げて直しています
- ループかどうか：Quaternius は名前の `_Loop`、KayKit は Idle・Pose・「〜ing」の名前（Chopping など）をループ、それ以外（Chop など）は 1 回再生
- `tools/make_motions.py` が `vrma/q/`（Quaternius）と `vrma/kk/medium/`・`vrma/kk/large/`（KayKit）を `motions.npz`（約 2.1 MB）に焼きます（30 fps、その場で動く形）。jump と ninja_jump は 開始 + 空中（0.4 秒）+ 着地 をつないでいます
- 骨ごとに「T ポーズからのワールド回転の差」を持たせているので、骨の長さや向きが違う VRM にもそのまま当てはまります（VRM 0.x は 180 度回してから当てます）
- ページのモーション一覧は、グループ分け・絞り込み・「All / Default / None」ボタン付きです。All は表示中（絞り込み後）のものを全部チェック、グループ名のクリックでそのグループを入 / 切
- Pyxel では、`pyxel.colors` を sheet.json の `palette` にしてから、各 PNG を `Image.from_image` で読むと色がずれません（サンプルはこの方法で、使うモーションの PNG だけ読みます）

## サンプルアバター（web/sample.vrm）

- 千駄ヶ谷 渋（VRoid の CC0 サンプルモデル。VRM のデータ作成者は coati。meta では再配布・改変とも可）
- `tools/make_sample_vrm.py` で軽くしたもの：テクスチャを 512 px 以下に縮め、表情（ブレンドシェイプ 456 個）を外しました。22 MB → 4.1 MB。形と骨は元のまま
- ほかのアバターは同梱しません（haruka_apps のアバターは作者のみ利用可・再配布禁止）

## しくみ

- `vrm_io.py`：VRM（GLB）を読みます。json・struct・numpy と、テクスチャだけ Pillow。0.x / 1.0 の meta と humanoid を読み分け、239 色のパレットを作ります
- `main.py`：Pyxel 3 の GLB 読み込みはスキンに非対応なので、numpy で CPU スキニングしています。スプライトは `Node.draw(..., target=画像)` で 1 コマずつ描いています
- `web/index.html`：`<pyxel-play packages="numpy,pillow">` で起動。ファイルは Pyodide の `/tmp/inbox/` に書き込み、ボタンの命令は `pyxel._vrmv` に積みます。Pyxel からは `js.vrmvInfo()` などでパネルを更新し、ダウンロードは `_savePyxelFile` を使います
- `tools/build_web.py`：main.py・vrm_io.py・sample_sprites.py・motions.npz・vrm_figure.py・sample_3d.py を .pyxapp にまとめ、itch 用 zip を作ります

## 確認したこと

クラウド（Linux、Pyxel 3.0.1 デスクトップ版）：
- VRM 1.0（千駄ヶ谷 渋）と VRM 0.x（自作）で表示、モーション切替、スプライト書き出し、3D 書き出し
- 231 モーションを 1 枚に並べて目で確認（8 本を外し、KayKit の腕を直した）
- スプライトの zip の中身、PNG・GIF の背景が透明なこと、書き出した sheet.json でサンプルが正しい色で動くこと
- 231 モーション全部のスプライト書き出し（64 px・8 方向・8 コマ）：153 秒、11.8 MB
- 3D 書き出し：0.7 秒、zip 約 2.9 MB。書き出したファイルだけで sample_3d.py が動き、`__file__` が無い環境でも動く
- 読み込み：千駄ヶ谷 渋 0.28 秒、0.x の自作（51,503 三角形）0.37 秒。スキニング約 7 ms

ブラウザ（作者が Mac で確認、Pyxel 3.0.1）：
- 上のバー・右のパネル・Try sample・絞り込み欄・All ボタン・進み具合のバー・書き出しとダウンロード
- 千駄ヶ谷 渋の読み込み 0.51 秒。231 モーション（128 px・8 方向・12 コマ）の書き出しで zip 48.3 MB

Code & Magic（作者が確認）：
- 書き出した 3D データ（model.tmx・motions.tmx・tex_*.png・vrm_figure.py・main.py）が動く

## 確認していないこと

- スマホでの表示
- Windows で HOW_TO_RUN.txt の手順どおりに動かすこと
- Safari・Firefox など、作者が使ったもの以外のブラウザ
- ブラウザでの書き出しの時間（測っていない）
