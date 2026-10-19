(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1000 (bvshl independent_opaque_0 (bvand (_ bv7 32) (_ bv31 32)))))
(let ((?x385 (bvadd ?x1000 independent_opaque_1)))
(let ((?x1257 (bvadd independent_opaque_1 ?x1000)))
(and (distinct ?x1257 ?x385) true)))))
(check-sat)
