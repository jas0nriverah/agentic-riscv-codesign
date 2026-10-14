(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x23 (bvshl independent_opaque_0 (bvand (_ bv15 32) (_ bv31 32)))))
(let ((?x48 (bvadd ?x23 independent_opaque_1)))
(let ((?x15 (bvadd independent_opaque_1 ?x23)))
(and (distinct ?x15 ?x48) true)))))
(check-sat)
