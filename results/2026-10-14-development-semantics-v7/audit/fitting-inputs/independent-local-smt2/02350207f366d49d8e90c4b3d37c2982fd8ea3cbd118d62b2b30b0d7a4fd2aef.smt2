(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1180 (bvshl independent_opaque_1 (bvand (_ bv13 32) (_ bv31 32)))))
(let ((?x980 (bvadd independent_opaque_0 ?x1180)))
(let ((?x392 (bvadd ?x1180 independent_opaque_0)))
(and (distinct ?x392 ?x980) true)))))
(check-sat)
