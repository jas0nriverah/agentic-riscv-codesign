(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x71 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x13 (bvadd independent_opaque_0 ?x71)))
(let ((?x74 (bvadd ?x71 independent_opaque_0)))
(and (distinct ?x74 ?x13) true)))))
(check-sat)
