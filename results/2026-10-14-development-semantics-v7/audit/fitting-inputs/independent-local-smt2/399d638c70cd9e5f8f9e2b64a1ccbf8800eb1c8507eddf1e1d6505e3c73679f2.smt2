(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x48 (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32)))))
(let ((?x505 (bvadd ?x48 independent_opaque_1)))
(let ((?x334 (bvadd independent_opaque_1 ?x48)))
(and (distinct ?x334 ?x505) true)))))
(check-sat)
