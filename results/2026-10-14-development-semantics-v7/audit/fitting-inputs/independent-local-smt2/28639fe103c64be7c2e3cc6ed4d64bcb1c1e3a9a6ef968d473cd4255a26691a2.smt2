(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x71 (bvshl independent_opaque_0 (bvand (_ bv14 32) (_ bv31 32)))))
(let ((?x84 (bvadd ?x71 independent_opaque_1)))
(let ((?x10 (bvadd independent_opaque_1 ?x71)))
(and (distinct ?x10 ?x84) true)))))
(check-sat)
