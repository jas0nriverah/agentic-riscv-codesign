(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x120 (bvshl y (_ bv8 32))))
(let ((?x116 (bvshl x (_ bv8 32))))
(let ((?x121 (bvadd ?x116 ?x120)))
(let ((?x19 (bvadd x y)))
(let ((?x119 (bvshl ?x19 (_ bv8 32))))
(and (distinct ?x119 ?x121) true)))))))
(check-sat)
