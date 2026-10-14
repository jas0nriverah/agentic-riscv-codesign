(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x10 (bvshl independent_opaque_0 (bvand (_ bv26 32) (_ bv31 32)))))
(let ((?x15 (bvadd ?x10 independent_opaque_1)))
(let ((?x47 (bvadd independent_opaque_1 ?x10)))
(and (distinct ?x47 ?x15) true)))))
(check-sat)
