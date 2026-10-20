// ocr_vision.swift — macOS Vision text recognition for tools/yanis_markers.py. [YANIS-MARKERS-V1 2026-10-19]
import Foundation
import Vision
import AppKit
// usage: ocr <png>... ; prints: file \t text \t conf \t x0 y0 x1 y1 (normalized, origin bottom-left)
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path), let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    req.minimumTextHeight = 0.004
    let h = VNImageRequestHandler(cgImage: cg, options: [:])
    try? h.perform([req])
    for o in (req.results ?? []) {
        guard let c = o.topCandidates(3).first else { continue }
        let alts = o.topCandidates(3).map { $0.string }.joined(separator: "|")
        let b = o.boundingBox
        print("\(path)\t\(c.string)\t\(c.confidence)\t\(b.minX) \(b.minY) \(b.maxX) \(b.maxY)\t\(alts)")
    }
}
