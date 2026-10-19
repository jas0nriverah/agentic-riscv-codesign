(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x126 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x85 (bvadd ?x126 independent_opaque_1)))
(let ((?x1246 (bvadd independent_opaque_1 ?x126)))
(and (distinct ?x1246 ?x85) true)))))
(check-sat)
