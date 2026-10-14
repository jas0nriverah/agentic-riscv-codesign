(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x392 (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x744 (bvadd independent_opaque_0 ?x392)))
(let ((?x514 (bvadd ?x392 independent_opaque_0)))
(and (distinct ?x514 ?x744) true)))))
(check-sat)
