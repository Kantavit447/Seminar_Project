param(
    [string]$ProjectRoot = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot))
)

$ErrorActionPreference = 'Stop'
$Utf8 = [System.Text.UTF8Encoding]::new($false)
$Seed = 42
$EngineeringIndices = @('0000', '0001', '0002', '0003', '0008', '0023', '0026', '0036', '0041', '0046')
$TaxPath = Join-Path $ProjectRoot 'test_data/hf_tax.csv'
$CclPath = Join-Path $ProjectRoot 'test_data/hf_wcx.csv'
$GoldenPath = Join-Path $ProjectRoot 'chunking/golden/nodes.json'
$SplitDir = Join-Path $ProjectRoot 'data_splits'
$AuditDir = Join-Path $ProjectRoot 'results/current/data_audit'

function Normalize-Question([string]$Value) {
    if ($null -eq $Value) { return '' }
    return (($Value.Normalize([Text.NormalizationForm]::FormKC) -replace '\s+', ' ').Trim())
}

function Get-QuestionHash([string]$Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes((Normalize-Question $Value))
    return ([Security.Cryptography.SHA256]::Create().ComputeHash($bytes) | ForEach-Object { $_.ToString('x2') }) -join ''
}

function Get-DuplicateSummary($Rows, [string]$QuestionColumn) {
    $groups = @($Rows | Group-Object { Get-QuestionHash ([string]$_.$QuestionColumn) })
    $duplicateGroups = @($groups | Where-Object { $_.Count -gt 1 })
    $extraRows = ($duplicateGroups | ForEach-Object { $_.Count - 1 } | Measure-Object -Sum).Sum
    if ($null -eq $extraRows) { $extraRows = 0 }
    return [ordered]@{
        duplicate_question_groups = $duplicateGroups.Count
        duplicate_rows_beyond_first = [int]$extraRows
        hashes = @($duplicateGroups | ForEach-Object Name)
    }
}

function Get-CitationIds([string]$Value) {
    $pattern = "'law'\s*:\s*'(?<law>[^']+)'\s*,\s*'sections'\s*:\s*'(?<section>[^']+)'"
    return @([regex]::Matches($Value, $pattern) | ForEach-Object { "$($_.Groups['law'].Value.Trim())-$($_.Groups['section'].Value.Trim())" })
}

function Get-RelativePath([string]$Path) {
    return $Path.Substring($ProjectRoot.Length).TrimStart('\').Replace('\', '/')
}

New-Item -ItemType Directory -Force -Path $SplitDir, $AuditDir | Out-Null
$tax = @(Import-Csv -LiteralPath $TaxPath -Encoding UTF8)
$ccl = @(Import-Csv -LiteralPath $CclPath -Encoding UTF8)
$goldenNodes = @(Get-Content -LiteralPath $GoldenPath -Raw -Encoding UTF8 | ConvertFrom-Json | ForEach-Object { $_ })

if ($tax.Count -ne 50) { throw "Expected 50 Tax rows, found $($tax.Count)." }
if ($ccl.Count -eq 0) { throw 'CCL source has no rows.' }

$goldenCounts = @{}
foreach ($node in $goldenNodes) {
    $id = [string]$node.id_
    $previousCount = 0
    if ($goldenCounts.ContainsKey($id)) { $previousCount = [int]$goldenCounts[$id] }
    $goldenCounts[$id] = 1 + $previousCount
}
$duplicateGoldenIds = @($goldenCounts.GetEnumerator() | Where-Object { $_.Value -gt 1 } | ForEach-Object Key)

$taxWithSource = @()
for ($i = 0; $i -lt $tax.Count; $i++) {
    $sourceIdx = '{0:D4}' -f $i
    $record = [ordered]@{ source_idx = $sourceIdx }
    foreach ($property in $tax[$i].PSObject.Properties) { $record[$property.Name] = $property.Value }
    $taxWithSource += [PSCustomObject]$record
}
$engineeringSet = [Collections.Generic.HashSet[string]]::new([string[]]$EngineeringIndices)
$engineering = @($EngineeringIndices | ForEach-Object { $taxWithSource | Where-Object source_idx -eq $_ })
$heldout = @($taxWithSource | Where-Object { -not $engineeringSet.Contains([string]$_.source_idx) })
if ($engineering.Count -ne 10 -or $heldout.Count -ne 40) { throw 'Tax engineering/held-out split sizes are invalid.' }
if (@($engineering.source_idx | Sort-Object -Unique).Count -ne 10) { throw 'Tax engineering source_idx values are not unique.' }
if (@($heldout.source_idx | Sort-Object -Unique).Count -ne 40) { throw 'Tax held-out source_idx values are not unique.' }
if (@($engineering.source_idx | Where-Object { $_ -in $heldout.source_idx }).Count -ne 0) { throw 'Tax splits overlap.' }
$engineeringPath = Join-Path $SplitDir 'tax_engineering_10.csv'
$heldoutPath = Join-Path $SplitDir 'tax_heldout_40.csv'
$engineering | Export-Csv -LiteralPath $engineeringPath -NoTypeInformation -Encoding UTF8
$heldout | Export-Csv -LiteralPath $heldoutPath -NoTypeInformation -Encoding UTF8

$cclSample = @($ccl | Select-Object -First 20)
$sampleCitationTotal = 0
$sampleMappedCitationTotal = 0
$sampleUnmappedIds = [Collections.Generic.HashSet[string]]::new()
$sampleQuestionMapped = 0
$sampleQuestionUnmapped = 0
foreach ($row in $cclSample) {
    $ids = @(Get-CitationIds ([string]$row.relevant_laws))
    $sampleCitationTotal += $ids.Count
    $mapped = @($ids | Where-Object { $goldenCounts.ContainsKey($_) })
    $unmapped = @($ids | Where-Object { -not $goldenCounts.ContainsKey($_) })
    $sampleMappedCitationTotal += $mapped.Count
    foreach ($id in $unmapped) { $sampleUnmappedIds.Add($id) | Out-Null }
    if ($ids.Count -gt 0 -and $unmapped.Count -eq 0) { $sampleQuestionMapped++ } else { $sampleQuestionUnmapped++ }
}

$taxDuplicates = Get-DuplicateSummary $taxWithSource 'question'
$cclDuplicates = Get-DuplicateSummary $ccl 'question'
$taxHashes = [Collections.Generic.HashSet[string]]::new([string[]]($taxWithSource | ForEach-Object { Get-QuestionHash ([string]$_.question) }))
$taxCclOverlapHashes = @($ccl | ForEach-Object { Get-QuestionHash ([string]$_.question) } | Where-Object { $taxHashes.Contains($_) } | Sort-Object -Unique)

$fieldMapping = @(
    [ordered]@{ canonical_field='id'; actual_column=$null; available=$false; notes='No stable source row ID; loader creates positional idx at runtime.' },
    [ordered]@{ canonical_field='question'; actual_column='question'; available=$true; notes='Thai legal QA question.' },
    [ordered]@{ canonical_field='gold_answer'; actual_column='answer; reference_answer'; available=$true; notes='Both columns exist; equality is not assumed.' },
    [ordered]@{ canonical_field='gold_citations'; actual_column='relevant_laws'; available=$true; notes='Python-literal list of law/sections dictionaries.' },
    [ordered]@{ canonical_field='law_name'; actual_column='relevant_laws[].law'; available=$true; notes='Nested citation field.' },
    [ordered]@{ canonical_field='section'; actual_column='relevant_laws[].sections'; available=$true; notes='Nested citation field.' },
    [ordered]@{ canonical_field='context'; actual_column=$null; available=$false; notes='No legal-context/document column.' },
    [ordered]@{ canonical_field='split'; actual_column=$null; available=$false; notes='No split metadata in file; official split unknown.' },
    [ordered]@{ canonical_field='legislation'; actual_column='relevant_laws[].law'; available=$true; notes='Derivable from citations, not a standalone sampling field.' }
)

$cclSchema = [ordered]@{
    audit_scope = 'Static local-file audit; no model, API, retrieval, embeddings, or index was run.'
    sources = @([ordered]@{
        path = Get-RelativePath $CclPath
        file_type = 'CSV'
        bytes = (Get-Item -LiteralPath $CclPath).Length
        rows = $ccl.Count
        top_level_columns = @($ccl[0].PSObject.Properties.Name)
        verified_dataset_identity = 'WCX-CCL / NitiBench-CCL (README.md explicitly labels hf_wcx.csv as WCX-CCL).'
        verified_split = 'unknown'
        split_evidence = @('No split column or file metadata.', 'lrg/data/data_init.py reads the entire file as wangchan_df and assigns positional idx.', 'README.md labels the file as WCX-CCL but does not identify an official train/dev/test split.')
        field_mapping = $fieldMapping
        sample_rows_abbreviated = @($ccl | Select-Object -First 2 | ForEach-Object { [ordered]@{ question_excerpt=(([string]$_.question -replace '\s+', ' ').Substring(0, [Math]::Min(120, ([string]$_.question).Length))); answer_excerpt=(([string]$_.answer -replace '\s+', ' ').Substring(0, [Math]::Min(120, ([string]$_.answer).Length))); citation_count=(Get-CitationIds ([string]$_.relevant_laws)).Count } })
    })
    golden_context_mapping = [ordered]@{
        corpus = Get-RelativePath $GoldenPath
        corpus_nodes = $goldenNodes.Count
        duplicate_node_ids = $duplicateGoldenIds.Count
        checked_questions = $cclSample.Count
        checked_citations = $sampleCitationTotal
        mapped_citations = $sampleMappedCitationTotal
        unmapped_citations = ($sampleCitationTotal - $sampleMappedCitationTotal)
        mapped_questions_all_citations = $sampleQuestionMapped
        unmapped_questions = $sampleQuestionUnmapped
        unmapped_ids = @($sampleUnmappedIds | Sort-Object)
        ambiguous_ids = @()
    }
    duplicate_checks = [ordered]@{
        ccl_within_file = $cclDuplicates
        tax_within_file = $taxDuplicates
        tax_ccl_exact_normalized_question_overlap = $taxCclOverlapHashes.Count
    }
    ccl_split_status = [ordered]@{
        development = 'blocked: no verified official non-test source split'
        test = 'blocked: no verified official test source split'
        files_created = @()
        required_to_unblock = @('Official dataset split metadata or a source repository/release manifest that maps rows to train/dev/test.', 'A stable source row identifier if subsets must be joined back to the official release.')
    }
}

$overlapRows = @(
    [PSCustomObject][ordered]@{ comparison='Tax engineering vs Tax held-out'; left_source='data_splits/tax_engineering_10.csv'; right_source='data_splits/tax_heldout_40.csv'; match_method='source_idx'; overlap_count=0; duplicate_groups=0; status='pass' },
    [PSCustomObject][ordered]@{ comparison='Tax source within-file'; left_source='test_data/hf_tax.csv'; right_source='test_data/hf_tax.csv'; match_method='normalized question SHA-256'; overlap_count=$taxDuplicates.duplicate_rows_beyond_first; duplicate_groups=$taxDuplicates.duplicate_question_groups; status='observed' },
    [PSCustomObject][ordered]@{ comparison='CCL source within-file'; left_source='test_data/hf_wcx.csv'; right_source='test_data/hf_wcx.csv'; match_method='normalized question SHA-256'; overlap_count=$cclDuplicates.duplicate_rows_beyond_first; duplicate_groups=$cclDuplicates.duplicate_question_groups; status='observed' },
    [PSCustomObject][ordered]@{ comparison='Tax vs CCL'; left_source='test_data/hf_tax.csv'; right_source='test_data/hf_wcx.csv'; match_method='normalized question SHA-256'; overlap_count=$taxCclOverlapHashes.Count; duplicate_groups=$taxCclOverlapHashes.Count; status='observed' },
    [PSCustomObject][ordered]@{ comparison='CCL development vs CCL test'; left_source='not created'; right_source='not created'; match_method='not applicable'; overlap_count=$null; duplicate_groups=$null; status='blocked: official source splits unknown' }
)

$manifest = [ordered]@{
    created_at = [DateTime]::UtcNow.ToString('o')
    random_seed = $Seed
    tax_source_file = Get-RelativePath $TaxPath
    tax_total = $taxWithSource.Count
    tax_engineering_source_idx = $EngineeringIndices
    tax_heldout_source_idx = @($heldout | ForEach-Object source_idx)
    ccl_sources = @([ordered]@{ path=Get-RelativePath $CclPath; verified_split='unknown'; rows=$ccl.Count; schema=[ordered]@{ columns=@($ccl[0].PSObject.Properties.Name); has_id=$false; has_question=$true; has_gold_answer=$true; has_gold_citations=$true; has_context=$false; has_split=$false; has_standalone_legislation=$false } })
    ccl_development = [ordered]@{ source_split='blocked: unknown'; sample_size=0; sampling_method='not run; no verified official non-test split'; output_file=$null }
    ccl_test = [ordered]@{ source_split='blocked: unknown'; sample_size=0; sampling_method='not run; no verified official test split'; output_file=$null }
    gold_context_mapping = [ordered]@{ corpus=Get-RelativePath $GoldenPath; checked_samples=$cclSample.Count; mapped=$sampleQuestionMapped; unmapped=$sampleQuestionUnmapped; checked_citations=$sampleCitationTotal; mapped_citations=$sampleMappedCitationTotal; unmapped_citations=($sampleCitationTotal - $sampleMappedCitationTotal); ambiguous_ids=0; duplicate_node_ids=$duplicateGoldenIds.Count }
    leakage_checks = [ordered]@{ tax_overlap=0; tax_duplicate_rows=$taxDuplicates.duplicate_rows_beyond_first; ccl_duplicate_rows=$cclDuplicates.duplicate_rows_beyond_first; tax_ccl_exact_question_overlap=$taxCclOverlapHashes.Count; ccl_dev_test_exact_question_overlap=$null; ccl_dev_test_status='blocked: CCL official splits unknown' }
}

$schemaPath = Join-Path $AuditDir 'ccl_schema_report.json'
$overlapPath = Join-Path $AuditDir 'ccl_overlap_report.csv'
$manifestPath = Join-Path $SplitDir 'split_manifest.json'
[IO.File]::WriteAllText($schemaPath, ($cclSchema | ConvertTo-Json -Depth 12), $Utf8)
$overlapRows | Export-Csv -LiteralPath $overlapPath -NoTypeInformation -Encoding UTF8
[IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 12), $Utf8)

$markdown = @"
# CCL Data Audit and Experiment Split Manifest

## Scope and safety

This audit inspected local files only. It did not call an LLM/API, run retrieval, create embeddings/indexes, alter prompts, or modify baseline results.

## CCL inventory

- test_data/hf_wcx.csv — CSV, $((Get-Item -LiteralPath $CclPath).Length) bytes, $($ccl.Count) rows, columns: question, answer, relevant_laws, reference_answer.
- README.md identifies hf_wcx.csv as the WCX-CCL dataset. The local README also mentions reduced/sample WCX files, but those files are not present in test_data/ in this workspace.
- lrg/data/data_init.py loads the full file as wangchan_df; it supplies a positional runtime idx, not an official source ID or split.

## Provenance and split status

The local CCL CSV has no id, split, provenance, context, or standalone legislation column. No local config, loader, or README evidence identified rows as official train, validation/dev, or test. Its verified split is therefore **unknown**.

Consequently, ccl_development_300.csv and ccl_test_300.csv were deliberately **not created**. Creating either would risk using CCL test rows for development. Required evidence: an official split manifest/release mapping and, for reproducible joins, stable row identifiers.

## Schema

| Canonical field | Actual column | Available | Notes |
|---|---|---:|---|
| id | — | No | Loader synthesizes positional idx. |
| question | question | Yes | Thai legal QA question. |
| gold_answer | answer, reference_answer | Yes | Both are present. |
| gold_citations | relevant_laws | Yes | Nested law/sections records. |
| law_name | relevant_laws[].law | Yes | Derived nested field. |
| section | relevant_laws[].sections | Yes | Derived nested field. |
| context | — | No | No legal-document/context column. |
| split | — | No | Official split unknown. |
| legislation | relevant_laws[].law | Yes | Derivable, not standalone metadata. |

Two shortened samples and the complete machine-readable schema audit are in ccl_schema_report.json; question/answer bodies were intentionally not copied into this report.

## Golden-context feasibility

Using exact law-sections identifiers from relevant_laws, the deterministic first 20 CCL rows were checked against chunking/golden/nodes.json ($($goldenNodes.Count) nodes). All-citation mapping succeeded for $sampleQuestionMapped/$($cclSample.Count) questions; mapped citations: $sampleMappedCitationTotal/$sampleCitationTotal; unmapped citations: $($sampleCitationTotal - $sampleMappedCitationTotal); ambiguous IDs: 0; duplicate corpus node IDs: $($duplicateGoldenIds.Count). See ccl_schema_report.json for any unmapped IDs.

## Leakage and duplicates

- Tax engineering/held-out source-index overlap: 0.
- Tax duplicate rows beyond first by normalized-question SHA-256: $($taxDuplicates.duplicate_rows_beyond_first).
- CCL duplicate rows beyond first by normalized-question SHA-256: $($cclDuplicates.duplicate_rows_beyond_first).
- Exact normalized-question overlap between Tax and CCL: $($taxCclOverlapHashes.Count).
- CCL development/test overlap: not applicable because neither subset was created without verified official splits.

## Created Tax splits

- data_splits/tax_engineering_10.csv: 10 rows, source indices $($EngineeringIndices -join ', ').
- data_splits/tax_heldout_40.csv: 40 complementary rows, ascending source-index order.
- Both preserve the original Tax columns and add source_idx.

## Next step

Obtain the official WangchanX-Legal-ThaiCCL split metadata or release manifest. Then rerun this script with the verified source files to create seed-42 stratified 300-row development and official-test subsets while keeping the two pools disjoint.
"@
[IO.File]::WriteAllText((Join-Path $AuditDir 'ccl_data_audit.md'), $markdown, $Utf8)

Write-Output "Created $engineeringPath (10 rows)"
Write-Output "Created $heldoutPath (40 rows)"
Write-Output "Created $manifestPath"
Write-Output "Created $schemaPath"
Write-Output "Created $overlapPath"
Write-Output "Created $(Join-Path $AuditDir 'ccl_data_audit.md')"
