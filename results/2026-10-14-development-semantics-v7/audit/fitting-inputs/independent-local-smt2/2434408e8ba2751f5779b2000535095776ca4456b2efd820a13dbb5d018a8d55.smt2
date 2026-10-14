(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1265 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv65536 32))))
(let ((?x126 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x895 (bvshl (bvadd independent_opaque_0 (_ bv1 32)) ?x126)))
(and (distinct ?x895 ?x1265) true)))))
(check-sat)
