(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_2 () (_ BitVec 32))
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x983 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv24 32) (_ bv31 32)))) (bvshl independent_opaque_2 (bvand (_ bv24 32) (_ bv31 32))))))
(let ((?x66 (bvadd independent_opaque_0 ?x983)))
(let ((?x1357 (bvand (_ bv24 32) (_ bv31 32))))
(let ((?x654 (bvsub independent_opaque_0 (bvshl (bvsub independent_opaque_1 independent_opaque_2) ?x1357))))
(and (distinct ?x654 ?x66) true))))))
(check-sat)
