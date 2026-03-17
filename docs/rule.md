6．メインコンペルール

メインコンベに係るルールになります。よく確認いただき参加するようお願いします。
Google Colabの無料ブラン（T4 GPU）で実行可能な範囲になっており、計算資源に限りがある方、LLMを学びたての方などにおすすめです．

------------------------------------------------------------------------------------------

6.1 メインコンペルール＿修了要件

メインコンベのスコアや提出物は他の講義の出席や宿題同様、購座の修了要件に関わります。䃓座修了 を目指される方は運営が公表する基準点（コンベ開始後に公開）以上を取るようにモデルの開発•改善を行い、提出をお願いします。

なお、Omnicampusのリーダーボードのスコアは提出の度に上書きとなり、最高点が常に表示されるわけ ではありません、ですが、DB上で受講生の過去のスコアは保持されているので、過去に出した最高点が基準点を超えていればOKです。（1度でも最高点が基準点を超えたことがあれぱOKです）

注意
- 基举点を超えたかどうかの個別の問合せには対応しませんので、党えておくようお臨いします。
- 過去の採点履歴を受講生側で見れるように対広予定ですが、保証するものではないので覚えておくようお願いします。
- あくまでも修了要件の1つです。必要条件であり、十分条件ではありません。
- 講議への出席や宿題の結果も加味して決定します。
- 基準点はこちらで提供するサンブルコードをパラメータの変更等で適切に改変を加えて実行できればクリアできる水準です。

------------------------------------------------------------------------------------------

6.2 メインコンペルール＿コンペの評価

メインコンベでは開発したモデルを用いて生成したjsonフアイルをOmnicampus上で提出すると、スコア が自動採点されます。採点結果は定期的にリーダーボードに反佒され、Omnicampus上で確認可能です。
最終的なスコアはコンベ終了のタイミングで別途計算され順位が決まります。評価の詳細はコンベ終了後、ランキング発表時に公開する予定です。
職切間近はアクセス集中でエラーが出ることがありますので、余㭲を持った提出を推翇します。提出回数は最大で50回（予定）としますので、計画的な提出を推奨します。


------------------------------------------------------------------------------------------


6.3 メインコンペルール＿ベンチマークの紹介

メインコンベでは、Struct Eval というベンチマークを一部改変した独自ベンチマークによる評伍を行いま す。
Struct Evalは、LLMにおける、權造化された出力を生成する能力を計るベンチマークです。
例：「これをjson形式で出力して」「json形式をyaml形式に変換して」など
Struct Evalベンチマークは、大きく分けて2つの評価セットで構案されています。
- Struct Eval－T ：テキスト生成を測る
- Struct Eval－V ：上販に加えて，レンダリングしたものの視覚的な評侣も行う

今回のコンベでは、Struct Eval－Tのみを対象として㙞価を行います。
LLMがコンビュータシステムやソフトウェア開発のAIエージェントワークフローにおいて、エラーなく蚛作する正確な構造データを生成できるかを試します。

Struct Eyal－Tのタスク例：json生成夕スク
例えば以下のようなプロンブトが与えられます

```
Please output JSON code．

Task：
Summarize metadata about a fictional scientific article．

Feature Requirements：
1．Top－level field＂title＂is a string
2．Field＂authors＂is a list of exactly two items
3．Each author has＂name＂and＂affiliation＂
4．Field＂publication year＂is an integer
5 ．Field＂keywords＂is a list of strings
```

これを受け取ったモデルは、以下のような出力が期待されます。
```
{
＂title＂：＂Temporal Anomalies in Sub－Atomic Particle Acceleration：A Case Study＂,
＂authors＂：［
	{
	＂name＂：＂Dr．Aris Thome＂,
	＂affiliation＂：＂Institute of Theoretical Chronophysics，Zurich＂
	},
	{
	＂name＂：＂Prof．Elena Voshkova＂,
	＂affiliation＂：＂Department of High Energy Physics，MIT＂ 
	}
 ],
 ＂publication＂：｛
 ＂year＂： 2028
 },
＂keywords＂：［
	＂Chronophysics＂,
	＂Particle Acceleration＂,
	＂Temporal Dilution＂,
	＂Quantum Mechanics＂
  ]
}

```

これに対して、JSONの仕様に沿っているかを判定する為の，以下のような採点基準がタスク毎にあります。
```
"raw_ouptut_metric":{
    "title",
    "authors[0]_name",
    "authors[1].affiliation",
    "publication_year",
    "keywords[2]"
}
```


これは以下のように考えます。
－title：トッブレベルにtitleがあるからOK
- authors［0］name：authorsの0番目にnameがあるからOK
- authors［1］．affiliation：authorsの1番目にaffiliationがあるからOK
- publication．year：ネストされたpublicationの中にyearがあるからOK
- keywords［2］：Keyword配列に3つ目の要素があるからOK
- ※入っている値は何でも良い

実際の評価デ一夕は以下のようになっており、row output metricが上で説明した採点基準の部分になり ます。

竍価データの一例
```
[
    {
        "task_id": "000500",
        "query": "Please output JSON code:\n\nTask:\n...",
        "feature_requirements": "",
        "task_name": "Text to JSON",
        "input_type": "Text",
        "output_type": "JSON",
        "query_example": "",
        "VQA": [],
        "raw_output_metric": [
            "novel.title",
            "novel.author.name",
            "novel.characters[0].name"
        ],
        "rendering": false
    }
]
```

それに対する推論は以下のようになっています。
推論結果の一例
```
[
    {
        "task_id": "000500",
        "query": "Please output 1SON code:\n\nTask:\n...",
        "feature requirements": "",
        "task_name": "Text to JSON",
        "input_type": "Text",
        "output_type": "]sow",
        "query_example": =",
        "VQA": [],
        "raw_output_metric": [--.].
        "rendering": false,
        "generation": "-"json\n{\n \"novel\": {\n \"title\": \"The Obsidian Labyrinth\",\n \"author
    }
1
```


LLMによる推論結果が＂generation＂として付与されており，この生成結果に対して，
- （この例では）JSONとしてパースできるか
- row＿output＿metricの採点基準をどれだけ満たしているか
で評価されます。

ただし、これはStructEval－Tオリジナルの評価データや評価方式であり、本コンペでは以下のような工夫 を加えています。
- row＿output＿metricを評価データからは分からないようにしている
- 評価システム（Omniキャンパス）にtask＿idと紐づけて埋め込んでいる
- 各タスクのrow＿output＿metricを変更している（採点基準を変えている）

本コンペにおいては、採点基準をコンペ参加者側から見えないようにし、さらに、採点基準自体を変更しています。
これにより、コンペ参加者が評価データの採点基準に特化した学習を行うことができないようになっています。（そもそもの話として、評価データを強く意識した学習はやめましょう）

その他にも
- 評価方法、アルゴリズムも概ねオリジナルと同じですが、コンベ用に一部変更を加えてます。
- コンペで使用する総合点については，形式毎の評価点を平均し、独自の重みづけを行って算出しています。

※ このため、オリジナルのSturuct Evalを回した場合と採点結果に多少差異が出るので注意してください
※ 評価の詳細は非公開とします。


学習のヒント
タスクの形式は、
- TEXT to **: 自然言語分の指示から、特定の形式に出力させる(生成タスク)
- ** to ++: 特定の形式から、特定に形式へ変換させる(変換タスク)
の２パターンです。
また、扱う形式は次の５種類です。
- JSON, YAML, TOMML, XML, CSV

本コンペでは、「指定された出力形式」で、「正しい構造を安定して生成する能力」を評価します。
よって、構文を壊さまい、要求されたキーを落とさない、余計な文章を出さない（コードだけ出すのが安全）ことを意識して、取り組んでください。


------------------------------------------------------------------------------------------

6.4 メインコンペルール＿提出物

参加者が提出するものは以下の2つです。
1．運営が提供する推論コードを用いて出力したJSONファイル
2．Hugging Faceにアップロードした，ご自身で開発したモデルのURL
a．運営がモデルを使用できるようpublicにすること．
b．READMEも記載してください。

1,2 両方とも、Omnicampusの提出ページより提出してください
タスクの入力であるjsonファイル（評価データ ：public＿150．json）は以下のような形式を含むファイルになってます。
```
"task id": "p.7b3394e21698627665533715",
"task_name": "Text to Jeovr,
*rendering"; false,
"query": "Please output JSON code:\n\nlask:\nSummarize a fictional ecosystem with detailed information about its clieate, species,
"output_type": "15xv"
),
```


運営が提供する推論コードを用いると出力として以下のようなjsonファイルが出力されます．対応するtask＿idに対して推論結果が＂generation＂として生成されています。
```
{
    "task_id": "p_7b3394e21698627665533715",
    "generation": "{\n \"ecosystem\": {\n \"namel": \"Luminara Tundra Ecosystem\",\n \"location\": {\n
},
```


こちら（inference．json というファイル名）を提出してください、
念のため、推論結果をDLした後、データを確認してみることをお勧めします。


------------------------------------------------------------------------------------------

6.5. メインコンペルール_運営からの配布物

メインコンペにおいて使用可能なデータセットは、運営において用意した次の10種類です。


SFT（標準コード1）用
	1-1. https://huggingface.co/datasets/u-10bei/structured_data_with_cot_dataset_512_v2
	1-2. https://huggingface.co/datasets/u-10bei/structured_data_with_cot_dataset_512_v4
	1-3. https://huggingface.co/datasets/u-10bei/structured_data_with_cot_dataset_512_v5
	1-4. 
	https://huggingface.co/datasets/u-10bei/structured_data_with_cot_dataset_512
	1-5. 
	https://huggingface.co/datasets/u-10bei/structured_data_with_cot_dataset_v2
	1-6. 
	https://huggingface.co/datasets/u-10bei/structured_data_with_cot_dataset
	2-1. https://huggingface.co/datasets/daichira/structured-3k-mix-sft
	2-2. https://huggingface.co/datasets/daichira/structured-5k-mix-sft
	2-3. https://huggingface.co/datasets/daichira/structured-hard-sft-4k

標準コード1では1-1を使用していますが、1-2以降を使用してもOKです。


DPO（標準コード3）用
	 https://huggingface.co/datasets/u-10bei/dpo-dataset-qwen-cot

注意
・このデータを使用するとスコアが上がることを保証するものではありません．
・ご自身で組み合わせたり，カスタマイズして使用してみてください．
　・ただし，詳細資料に記載してあるルールは守ってください．
・データの追加の可能性はございます．
　・その場合は運営からアナウンスいたします．


------------------------------------------------------------------------------------------

6.6.1 メインコンペルール＿モデル関連

開発するモデルに係る制約事項は以下です。
	－本コンベにおける学習指定モデルは以下です
	－Qwen／Qwen3－4B－Instruct－2507
	－unsloth／Qwen3－4B－Instruct－2507
	- これ以外のモデルの使用は認めません．派生モデルも禁止です

- 提出するモテルは学習指定モデルを学習したモデルであること、
	- モテルアーキテクチャの変更は認めません

- 捉出するモデルはHugging Faceにモデルとしてアップロード可能であること
	- WRITE権限のキーが必要になります。取得方法は補足資料＞HuggingFace のトークン取得方法を確認ください

- 提出するモテルには必ず何かしらの変更を加える必要があります
	- SFTやRLHF、DPOなどによりバラメータを更新すればその条件を淒たします
	- 量子化も変更にあたります

- モテル開発のあらゆる段階でStructEvalのデータを用いることを禁止します
	- 運営が提供する評価データは勿論，オリジナルのStructEvalのデータを用いることも禁止

- リーダーボードを利用したチューニングを禁止します

------------------------------------------------------------------------------------------

6.6.2 メインコンペルール＿学習データ関連

モデルの学習に用いるデータに係る制約事項は以下です。

- 運営が提供、または紹介する学習データ以外の使用は禁止です
	- 運営が提供する、または紹介するデータの範囲で学習を行ってください
- LLMを用いたテータの作成は禁止です
	- 運営が提供、または紹介するデータをLLMを用いて改変したり、合成することは禁止です
- LLMを用いないデータ作成は可とします
	- 詳細は補足資料をこ確認ください
		- 補足資料＞LLMモデル開発におけるお約束
		- 補足資料＞LLMによるデータ作成
	- 例えば、運営が提供する、または紹介するデータをLLMを用いず改変することは可能です
